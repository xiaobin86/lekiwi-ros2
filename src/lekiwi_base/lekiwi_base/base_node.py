#!/usr/bin/env python3
"""
树莓派端底盘驱动节点：接收 /cmd_vel，调用 LeRobot 驱动底盘。

【ROS2 架构说明】
================
这是一个标准的 ROS2 Node，运行在树莓派上，负责：
1. 订阅 /cmd_vel（来自 PC 端的速度指令）
2. 通过 LeRobot API 控制底盘运动
3. 提供看门狗安全保护
4. (可选) 读取摄像头并发布图像

【ROS2 核心概念在本文件中的体现】
-----------------------------------
1. Node: 继承 rclpy.node.Node，是 ROS2 计算图的基本单元
2. Parameters: 使用 declare_parameter() 声明可配置参数
3. Subscribers: create_subscription() 订阅 /cmd_vel
4. Publishers: create_publisher() 发布图像
5. Timers: create_timer() 创建周期性回调（控制循环、看门狗）
6. QoS: 发布/订阅时的服务质量配置
7. Logging: get_logger() 分级日志系统
8. Clock: get_clock() 获取 ROS2 时间（支持仿真时间）

【多线程设计说明】
------------------
我们使用 Python threading 而非 ROS2 MultiThreadedExecutor，原因：
- ROS2 主循环（rclpy.spin）保持单线程，处理 ROS2 回调
- 摄像头读取在独立后台线程，避免阻塞控制循环
- 详见 docs/architecture/multithreading-analysis.md

【坐标系说明】
--------------
ROS2 标准: Twist.angular.z 使用 rad/s
LeRobot 内部: theta.vel 使用 deg/s
转换: math.degrees(rad) -> deg
"""

import math
import threading
import time
import numpy as np
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Image
from builtin_interfaces.msg import Time
from cv_bridge import CvBridge


class LekiwiBaseNode(Node):
    """LeKiwi 底盘驱动节点。
    
    【Node 生命周期】
    在 ROS2 中，Node 是有生命周期的对象：
    1. 创建: __init__() - 初始化所有资源
    2. 配置: 声明参数、创建发布/订阅/定时器
    3. 激活: 节点开始处理回调
    4. 销毁: destroy_node() - 清理资源
    
    【重要】Node 名称必须唯一。如果启动两个同名节点，
    ROS2 会自动在名称后加数字后缀（如 lekiwi_base_node_1）
    """

    def __init__(self):
        """节点构造函数。
        
        【ROS2 参数系统】
        ROS2 使用声明式参数（Declarative Parameters）：
        - 必须先 declare_parameter() 声明，才能使用
        - 参数可以在运行时通过命令行、launch 文件、或 rqt_reconfigure 修改
        - 参数有类型检查（int, float, string, bool, list 等）
        
        声明参数的方式：
        declare_parameter(name, default_value, descriptor)
        
        读取参数的方式：
        value = get_parameter(name).value
        
        示例（命令行覆盖参数）：
        python -m lekiwi_base.base_node --ros-args -p use_cameras:=true -p port:=/dev/ttyACM1
        """
        super().__init__('lekiwi_base_node')
        
        # ============================================================
        # 1. 声明参数（必须在创建发布者/订阅者之前）
        # ============================================================
        # port: 串口设备路径。Linux 上通常是 /dev/ttyACM0 或 /dev/ttyUSB0
        self.declare_parameter('port', '/dev/ttyACM0')
        
        # robot_id: LeRobot 机器人的唯一标识符
        self.declare_parameter('robot_id', 'lekiwi')
        
        # watchdog_timeout_ms: 看门狗超时时间（毫秒）
        # 如果超过这个时间没有收到 /cmd_vel，底盘自动停止
        self.declare_parameter('watchdog_timeout_ms', 500)
        
        # control_freq: 控制循环频率（Hz）
        # 30Hz = 每 33ms 发送一次指令给底盘
        self.declare_parameter('control_freq', 30.0)
        
        # use_cameras: 是否启用摄像头
        # 默认 False，因为 Phase 1 不需要摄像头
        self.declare_parameter('use_cameras', False)

        # ============================================================
        # 2. 读取参数值
        # ============================================================
        port = self.get_parameter('port').value
        robot_id = self.get_parameter('robot_id').value
        self.watchdog_timeout_ms = self.get_parameter('watchdog_timeout_ms').value
        self.use_cameras = self.get_parameter('use_cameras').value

        # ============================================================
        # 3. 初始化硬件（LeRobot）
        # ============================================================
        # 注意：硬件初始化在 ROS2 通信之前，确保硬件就绪后才能处理消息
        self._init_lerobot(port, robot_id)

        # ============================================================
        # 4. 创建 ROS2 通信接口
        # ============================================================
        # 
        # 【订阅者 Subscriber】
        # create_subscription(msg_type, topic_name, callback, qos_profile)
        # 
        # - msg_type: 消息类型（如 Twist）
        # - topic_name: 话题名称（如 /cmd_vel）
        # - callback: 回调函数，收到消息时自动调用
        # - qos_profile: 服务质量配置（整数 = 队列深度，或用 QoSProfile 对象）
        # 
        # 【QoS 说明】
        # QoS (Quality of Service) 控制消息传输的可靠性：
        # - Reliability: RELIABLE（确保送达）或 BEST_EFFORT（尽力而为，低延迟）
        # - Durability: VOLATILE（只发给在线订阅者）或 TRANSIENT_LOCAL（持久化）
        # - History: KEEP_LAST(n)（保留最近 n 个）或 KEEP_ALL（保留所有）
        # 
        # 对于实时控制指令，通常使用 BEST_EFFORT + KEEP_LAST(1)：
        # 这样总是处理最新指令，而不是排队处理旧指令
        
        self.cmd_sub = self.create_subscription(
            Twist,           # 消息类型: geometry_msgs/Twist
            '/cmd_vel',      # 话题名称
            self.cmd_vel_callback,  # 回调函数
            10               # QoS: 队列深度 10（简单场景用整数即可）
        )
        
        # 【定时器 Timer】
        # create_timer(period_sec, callback)
        # 
        # ROS2 定时器不是线程，而是在 executor 的事件循环中调度。
        # 当 spin() 运行时，定时器到期会触发回调。
        # 
        # 看门狗定时器：每 250ms 检查一次是否超时
        # 超时时间的一半 = 500ms / 2 = 250ms
        self.last_cmd_time = self.get_clock().now()
        watchdog_period = self.watchdog_timeout_ms / 1000.0 / 2.0
        self.watchdog_timer = self.create_timer(watchdog_period, self.watchdog_callback)
        
        # 控制循环定时器：按 control_freq 频率发送指令
        # 30Hz = 1/30 ≈ 0.033s
        control_period = 1.0 / self.get_parameter('control_freq').value
        self.control_timer = self.create_timer(control_period, self.control_callback)

        # ============================================================
        # 5. 初始化状态变量
        # ============================================================
        # current_action: 缓存当前要发送给底盘的动作指令
        # 每次收到 /cmd_vel 时更新
        self.current_action = self._make_zero_action()
        self.action_lock = False  # 预留的锁标志（当前未使用）

        # ============================================================
        # 6. 初始化摄像头（可选）
        # ============================================================
        # 【发布者 Publisher】
        # create_publisher(msg_type, topic_name, qos_profile)
        # 
        # 发布者用于向话题发送消息。任何订阅了该话题的节点都能收到。
        # 这里是图像发布者，用于发布摄像头图像。
        
        self.image_pubs = {}  # 字典: {'front': publisher, 'wrist': publisher}
        self.bridge = None    # CvBridge: OpenCV 图像 ↔ ROS2 Image 消息转换器
        
        if self.use_cameras:
            # CvBridge 是 ROS2 和 OpenCV 之间的桥梁
            # 它将 numpy.ndarray (OpenCV 格式) 转换为 sensor_msgs/Image
            self.bridge = CvBridge()
            
            # front 摄像头发布者
            self.image_pubs['front'] = self.create_publisher(
                Image,                        # 消息类型
                '/camera/front/image_raw',    # 话题名称
                10                            # QoS 队列深度
            )
            
            # wrist 摄像头发布者
            self.image_pubs['wrist'] = self.create_publisher(
                Image,
                '/camera/wrist/image_raw',
                10
            )
            
            self.get_logger().info(
                '摄像头图像将发布到: /camera/front/image_raw, /camera/wrist/image_raw'
            )

        # ============================================================
        # 7. 启动摄像头后台线程（关键设计决策）
        # ============================================================
        # 【为什么用 threading 而不是 ROS2 Timer？】
        # 
        # ROS2 的 Timer 回调在 executor 的同一个线程中顺序执行。
        # 如果我们在 Timer 回调中调用 get_observation() 读取摄像头，
        # 而 get_observation() 内部也访问串口（与 send_action 冲突），
        # 就会导致控制延迟。
        # 
        # 解决方案：
        # - 控制回调（control_callback）在 ROS2 主线程中执行
        # - 摄像头读取在独立的 Python 线程中执行
        # - 两者互不阻塞
        # 
        # 【daemon=True 说明】
        # daemon 线程是守护线程，主程序退出时会自动终止。
        # 这样不需要手动 join，避免程序卡住。
        
        self.camera_thread = None
        self.camera_running = False
        if self.use_cameras:
            self.camera_running = True
            self.camera_thread = threading.Thread(
                target=self._camera_loop,
                daemon=True  # 守护线程，主程序退出时自动终止
            )
            self.camera_thread.start()
            self.get_logger().info('摄像头后台线程已启动')

        # 节点启动完成日志
        self.get_logger().info(
            f'LekiwiBaseNode started. '
            f'Port: {port}, Watchdog: {self.watchdog_timeout_ms}ms, '
            f'Cameras: {self.use_cameras}'
        )

    def _init_lerobot(self, port: str, robot_id: str):
        """初始化 LeRobot LeKiwi。
        
        【LeRobot 架构说明】
        LeRobot 是 HuggingFace 开源的机器人学习框架：
        - LeKiwi: 具体的机器人类，封装了底盘控制
        - LeKiwiConfig: 配置类，定义串口、摄像头、电机等参数
        - connect(): 打开串口、初始化电机、校准等
        
        【摄像头配置】
        摄像头通过 OpenCVCameraConfig 配置：
        - index_or_path: 设备路径（Linux: /dev/video0, /dev/video2）
        - width/height: 分辨率
        - fps: 帧率
        - warmup_s: 预热时间（摄像头启动后等待曝光稳定）
        - rotation: 图像旋转（ROTATE_90, ROTATE_180 等）
        """
        try:
            from lerobot.robots.lekiwi import LeKiwi
            from lerobot.robots.lekiwi.config_lekiwi import LeKiwiConfig
            from lerobot.cameras.opencv import OpenCVCameraConfig
            from lerobot.cameras import Cv2Rotation
        except ImportError as e:
            self.get_logger().fatal(f'Failed to import LeRobot: {e}')
            raise

        try:
            config = LeKiwiConfig(port=port, id=robot_id)
            if not self.use_cameras:
                config.cameras = {}  # Phase 1 禁用摄像头
            else:
                # 摄像头详细配置
                config.cameras = {
                    "front": OpenCVCameraConfig(
                        index_or_path="/dev/video2",    # front 摄像头设备
                        width=640,                       # 宽度（像素）
                        height=480,                      # 高度（像素）
                        fps=30,                          # 帧率
                        warmup_s=3,                      # 预热 3 秒（曝光稳定）
                        rotation=Cv2Rotation.ROTATE_180, # 旋转 180 度（安装方向）
                    ),
                    "wrist": OpenCVCameraConfig(
                        index_or_path="/dev/video0",    # wrist 摄像头设备
                        width=480,
                        height=640,
                        fps=30,
                        warmup_s=3,
                        rotation=Cv2Rotation.ROTATE_90, # 旋转 90 度
                    ),
                }
                self.get_logger().info(
                    '摄像头配置: front=/dev/video2 (640x480, rot=180), '
                    'wrist=/dev/video0 (480x640, rot=90), warmup=3s'
                )

            self.robot = LeKiwi(config)
            self.robot.connect()  # 连接串口，初始化电机
            self.get_logger().info('LeKiwi connected successfully')
        except Exception as e:
            self.get_logger().fatal(f'Failed to connect LeKiwi: {e}')
            raise

    # 【类属性】机械臂默认姿态
    # 使用类属性而非实例属性，因为所有实例共享相同的默认值
    ARM_DEFAULTS = {
        "arm_shoulder_pan.pos": 0.0,
        "arm_shoulder_lift.pos": -100.0,
        "arm_elbow_flex.pos": 90.0,
        "arm_wrist_flex.pos": 70.0,
        "arm_wrist_roll.pos": 0.0,
        "arm_gripper.pos": 0.0,
    }

    def _make_zero_action(self) -> dict:
        """创建零动作字典（停止底盘运动，但保持机械臂默认姿态）。
        
        【LeRobot Action 格式】
        LeRobot 使用字典作为 action，键是电机名称+属性：
        - *.pos: 位置控制（度）
        - *.vel: 速度控制（底盘: m/s, deg/s）
        
        对于底盘：
        - x.vel: 前进/后退速度 (m/s)
        - y.vel: 左/右平移速度 (m/s)
        - theta.vel: 旋转速度 (deg/s)
        """
        action = dict(self.ARM_DEFAULTS)  # 复制默认机械臂姿态
        action.update({
            "x.vel": 0.0,
            "y.vel": 0.0,
            "theta.vel": 0.0,
        })
        return action

    def cmd_vel_callback(self, msg: Twist):
        """收到 /cmd_vel 回调函数。
        
        【ROS2 回调机制】
        当有人发布消息到 /cmd_vel 时，ROS2 会自动调用此函数。
        回调函数签名：callback(msg: MessageType)
        
        【线程安全】
        在单线程 executor 中，回调是顺序执行的，不需要锁。
        但如果有多个线程（如 MultiThreadedExecutor），需要保护共享数据。
        
        【单位转换】
        ROS2 Twist: angular.z 是 rad/s
        LeRobot: theta.vel 是 deg/s
        转换: deg = rad * 180 / π
        """
        action = self._make_zero_action()
        action["x.vel"] = msg.linear.x           # m/s
        action["y.vel"] = msg.linear.y           # m/s
        action["theta.vel"] = math.degrees(msg.angular.z)  # rad/s → deg/s

        self.current_action = action
        self.last_cmd_time = self.get_clock().now()

    def control_callback(self):
        """控制循环定时器回调。
        
        【定时器调度】
        ROS2 定时器由 executor 的事件循环调度。
        当 spin() 运行时，定时器到期会自动触发回调。
        
        【频率】
        30Hz = 每秒 30 次 = 每 33ms 一次
        如果回调执行时间超过 33ms，下一次会延迟触发（不会堆积）。
        
        【设计原则】
        控制回调应该尽可能快，只做必要的事：
        1. 读取缓存的动作指令（self.current_action）
        2. 发送给底盘（send_action）
        不在这里做耗时操作（如图像处理、日志打印）。
        """
        try:
            self.robot.send_action(self.current_action)
        except Exception as e:
            self.get_logger().error(f'Failed to send action: {e}')

    def _camera_loop(self):
        """摄像头后台线程循环。
        
        【为什么用独立线程？】
        1. 摄像头读取可能耗时（USB 传输、图像解码）
        2. 如果放在 ROS2 Timer 回调中，会阻塞控制循环
        3. 独立线程保证控制循环的实时性
        
        【与 ROS2 的关系】
        这个线程是普通的 Python 线程，不是 ROS2 的组件。
        但它使用 ROS2 发布者（self.image_pubs）发布图像。
        
        【注意】
        rclpy 的发布者不是线程安全的！
        虽然这里我们在单线程 ROS2 executor 中运行，
        但如果未来改为 MultiThreadedExecutor，
        需要确保发布者和订阅者的线程安全。
        
        【当前实现】
        我们直接读取摄像头（cam.read_latest()），
        不通过 get_observation()（避免串口冲突）。
        """
        self.get_logger().info('Camera thread started')
        frame_count = 0

        while self.camera_running and rclpy.ok():
            if not self.use_cameras or not self.image_pubs:
                time.sleep(0.1)
                continue

            try:
                # 直接读取摄像头，不通过 get_observation()
                # 原因：get_observation() 会读取电机位置（访问串口），
                # 与 send_action() 冲突，导致 "Port is in use" 错误
                observation = {}
                for cam_key, cam in self.robot.cameras.items():
                    observation[cam_key] = cam.read_latest()
                
                frame_count += 1
                if frame_count % 30 == 0:  # 每3秒打印一次调试信息
                    self.get_logger().info(
                        f'Camera thread alive, frames={frame_count}, '
                        f'cameras={list(observation.keys())}'
                    )

                self._publish_camera_images(observation)
            except Exception as e:
                self.get_logger().warning(f'Camera thread error: {e}')

            time.sleep(0.1)  # 10Hz

    def _publish_camera_images(self, observation: dict):
        """发布摄像头图像到 ROS2 Topic。
        
        【CvBridge 说明】
        CvBridge 是 ROS 和 OpenCV 之间的桥梁：
        - cv2_to_imgmsg(): OpenCV 图像(numpy) → ROS Image 消息
        - imgmsg_to_cv2(): ROS Image 消息 → OpenCV 图像(numpy)
        
        【Image 消息格式】
        sensor_msgs/Image:
        - header: 时间戳和坐标系
        - height, width: 图像尺寸
        - encoding: 编码格式（如 'bgr8', 'rgb8', 'mono8'）
        - step: 每行字节数
        - data: 原始图像数据（字节数组）
        
        【OpenCV 格式】
        OpenCV 默认使用 BGR 格式（Blue-Green-Red），
        而大多数图像库使用 RGB。
        在 PC 端显示时可能需要转换。
        """
        try:
            # 发布 front 摄像头
            if 'front' in observation and 'front' in self.image_pubs:
                front_img = observation['front']
                if isinstance(front_img, np.ndarray) and front_img.ndim == 3:
                    # OpenCV 图像(H, W, C) → ROS Image 消息
                    img_msg = self.bridge.cv2_to_imgmsg(front_img, encoding='bgr8')
                    
                    # 设置消息头（时间戳和坐标系）
                    # stamp: 当前 ROS2 时间
                    # frame_id: 坐标系名称（用于 TF 变换）
                    img_msg.header.stamp = self.get_clock().now().to_msg()
                    img_msg.header.frame_id = 'front_camera'
                    
                    self.image_pubs['front'].publish(img_msg)

            # 发布 wrist 摄像头
            if 'wrist' in observation and 'wrist' in self.image_pubs:
                wrist_img = observation['wrist']
                if isinstance(wrist_img, np.ndarray) and wrist_img.ndim == 3:
                    img_msg = self.bridge.cv2_to_imgmsg(wrist_img, encoding='bgr8')
                    img_msg.header.stamp = self.get_clock().now().to_msg()
                    img_msg.header.frame_id = 'wrist_camera'
                    self.image_pubs['wrist'].publish(img_msg)

        except Exception as e:
            self.get_logger().warning(f'Failed to publish camera image: {e}')

    def watchdog_callback(self):
        """看门狗定时器回调。
        
        【安全机制】
        看门狗是一种安全保护机制：
        如果超过设定时间没有收到新的速度指令，
        自动停止底盘，防止失控。
        
        【为什么需要？】
        1. 网络断开：PC 和树莓派之间的 WiFi 连接中断
        2. 程序崩溃：PC 端的 joy_node 崩溃
        3. 人为错误：忘记停止程序就离开
        
        【实现方式】
        1. 每次收到 /cmd_vel 时，更新 last_cmd_time
        2. 看门狗定期检查：now - last_cmd_time > timeout?
        3. 如果超时，发送零速度指令
        
        【ROS2 Time】
        get_clock().now() 返回 ROS2 时间，支持仿真时间（如在 Gazebo 中）。
        与 Python time.time() 不同，ROS2 Time 可以被仿真器控制。
        
        Duration 用于时间计算：
        duration = rclpy.duration.Duration(seconds=0.5)
        """
        now = self.get_clock().now()
        timeout = rclpy.duration.Duration(
            seconds=self.watchdog_timeout_ms / 1000.0
        )

        if now - self.last_cmd_time > timeout:
            # 检查当前是否在运动（避免重复打印日志）
            if self.current_action["x.vel"] != 0.0 or \
               self.current_action["y.vel"] != 0.0 or \
               self.current_action["theta.vel"] != 0.0:
                self.get_logger().warning(
                    f'Watchdog timeout ({self.watchdog_timeout_ms}ms)! Stopping base.'
                )
                zero_action = self._make_zero_action()
                try:
                    self.robot.send_action(zero_action)
                    self.current_action = zero_action
                except Exception as e:
                    self.get_logger().error(f'Failed to stop base: {e}')

    def destroy_node(self):
        """销毁节点，清理资源。
        
        【ROS2 生命周期】
        当节点被销毁时（如按 Ctrl+C），ROS2 会调用 destroy_node()。
        这里我们需要：
        1. 停止摄像头线程（避免线程泄漏）
        2. 停止底盘（安全停车）
        3. 断开硬件连接
        4. 调用父类的 destroy_node()（清理 ROS2 资源）
        
        【线程清理】
        daemon=True 的线程会在主程序退出时自动终止，
        但我们仍然应该优雅地停止它，避免资源泄漏。
        """
        self.get_logger().info('Shutting down, stopping base...')

        # 停止摄像头线程
        if self.camera_thread is not None:
            self.camera_running = False  # 设置标志，让线程自然退出
            self.camera_thread.join(timeout=1.0)  # 等待最多 1 秒

        try:
            self.robot.stop_base()  # 停止底盘运动
            self.robot.disconnect()  # 断开串口连接
        except Exception as e:
            self.get_logger().error(f'Error during shutdown: {e}')
        
        super().destroy_node()  # 调用父类清理 ROS2 资源


def main(args=None):
    """ROS2 节点入口函数。
    
    【标准模式】
    所有 ROS2 Python 节点都遵循这个模式：
    1. rclpy.init(): 初始化 ROS2 客户端库
    2. 创建节点对象
    3. rclpy.spin(): 进入事件循环，处理回调
    4. 清理资源
    
    【spin() 的作用】
    spin() 是阻塞调用，它会：
    - 监听订阅者，收到消息时调用回调
    - 检查定时器，到期时调用回调
    - 处理服务请求（如果有 Service）
    - 处理动作目标（如果有 Action）
    
    spin() 会一直运行，直到：
    - 收到 KeyboardInterrupt (Ctrl+C)
    - 调用 rclpy.shutdown()
    - 节点被销毁
    
    【为什么用 try/finally？】
    确保即使发生异常，也能正确清理资源（关闭硬件、释放内存）。
    """
    rclpy.init(args=args)  # 初始化 ROS2
    node = LekiwiBaseNode()  # 创建节点
    try:
        rclpy.spin(node)  # 进入事件循环
    except KeyboardInterrupt:
        pass  # 用户按 Ctrl+C，正常退出
    finally:
        node.destroy_node()  # 销毁节点
        rclpy.shutdown()  # 关闭 ROS2


if __name__ == '__main__':
    main()
