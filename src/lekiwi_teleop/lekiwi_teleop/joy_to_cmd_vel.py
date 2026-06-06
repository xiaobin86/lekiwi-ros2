#!/usr/bin/env python3
"""
Joy → CmdVel 转换节点：将手柄输入转换为底盘速度指令。

【ROS2 架构说明】
================
这是一个典型的 ROS2 "转换节点"（Transformer Node）：
- 订阅一个 Topic（/joy）
- 进行数据转换（手柄状态 → 速度指令）
- 发布到另一个 Topic（/cmd_vel）

【ROS2 核心概念】
-----------------
1. Node: 继承 rclpy.node.Node
2. Subscribers: 订阅 /joy（手柄原始输入）
3. Publishers: 发布 /cmd_vel（底盘速度指令）
4. Parameters: 可配置的速度缩放、死区等
5. Message Types:
   - sensor_msgs/Joy: 手柄状态（axes + buttons）
   - geometry_msgs/Twist: 速度指令（linear + angular）

【坐标系说明】
--------------
底盘坐标系（Body Frame）：
- X 轴: 前进方向（正 = 前进）
- Y 轴: 左方（正 = 左平移）
- Z 轴: 上方（正 = 逆时针旋转）

ROS2 标准 Twist 消息：
- linear.x: 前进/后退速度 (m/s)
- linear.y: 左/右平移速度 (m/s)
- angular.z: 偏航角速度 (rad/s)

【手柄映射说明】
----------------
使用 joy_node（SDL2）读取手柄，D-pad 映射为 hat：
- axes[6] = hat_x: D-pad 左右（左=+1, 右=-1）
- axes[7] = hat_y: D-pad 上下（上=+1, 下=-1）
- buttons[7] = RB: 右肩键（用于切换旋转模式）

注意：SDL2 的 hat_x 极性与 pygame 相反！
- pygame: 左=-1, 右=+1
- SDL2 joy_node: 左=+1, 右=-1
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from geometry_msgs.msg import Twist


class JoyToCmdVel(Node):
    """Joy 到 CmdVel 转换节点。
    
    【设计模式】
    这是一个"转换器"节点，遵循 ROS2 的数据流设计模式：
    Input → Process → Output
    /joy  → 映射   → /cmd_vel
    
    【性能考虑】
    回调函数应该尽可能轻量：
    - 只做简单的数学计算
    - 避免文件 I/O、网络请求
    - 避免复杂的数据结构操作
    
    因为 joy_node 发布频率通常 50-100Hz，
    如果回调太慢，会丢失输入或造成延迟。
    """

    def __init__(self):
        """节点构造函数。
        
        【参数设计】
        使用 ROS2 参数系统，允许运行时调整：
        - linear_scale: 线速度最大值（m/s）
        - angular_scale: 角速度最大值（rad/s）
        - deadzone: 死区（忽略小输入，避免抖动）
        
        运行时调整示例：
        ros2 param set /joy_to_cmd_vel linear_scale 0.3
        """
        super().__init__('joy_to_cmd_vel')

        # ============================================================
        # 1. 创建通信接口
        # ============================================================
        
        # 【订阅者】订阅 /joy（手柄输入）
        # Joy 消息结构：
        #   axes: float32[]    - 模拟输入（摇杆、扳机、hat）
        #   buttons: int32[]   - 数字输入（按钮）
        self.sub = self.create_subscription(
            Joy,              # 消息类型
            '/joy',           # 话题名称
            self.joy_callback,# 回调函数
            10                # QoS 队列深度
        )
        
        # 【发布者】发布 /cmd_vel（速度指令）
        # Twist 消息结构：
        #   linear: Vector3 (x, y, z)  - 线速度 (m/s)
        #   angular: Vector3 (x, y, z) - 角速度 (rad/s)
        self.pub = self.create_publisher(
            Twist,            # 消息类型
            '/cmd_vel',       # 话题名称
            10                # QoS 队列深度
        )

        # ============================================================
        # 2. 声明参数
        # ============================================================
        # linear_scale: 线速度最大值（m/s）
        # 默认 0.5 m/s ≈ 1.8 km/h，适合室内操作
        self.declare_parameter('linear_scale', 0.5)
        
        # angular_scale: 角速度最大值（rad/s）
        # 默认 1.0 rad/s ≈ 57 deg/s
        self.declare_parameter('angular_scale', 1.0)
        
        # deadzone: 死区阈值
        # 小于此值的输入被忽略，避免手柄漂移造成误动作
        self.declare_parameter('deadzone', 0.1)

        # 读取参数值
        self.linear_scale = self.get_parameter('linear_scale').value
        self.angular_scale = self.get_parameter('angular_scale').value
        self.deadzone = self.get_parameter('deadzone').value

        self.get_logger().info(
            f'Joy→CmdVel 启动 | '
            f'linear_scale={self.linear_scale}, '
            f'angular_scale={self.angular_scale}, '
            f'deadzone={self.deadzone}'
        )

    def apply_deadzone(self, value):
        """应用死区。
        
        【作用】
        手柄摇杆/方向键在中心位置时可能不是严格的 0，
        而是有一个小的偏移（如 0.02）。
        死区可以忽略这些小偏移，避免底盘无故运动。
        
        【实现】
        如果 |value| < deadzone，返回 0
        否则返回原始值
        
        注意：当前代码中没有使用这个函数，
        因为 D-pad（hat）的值是离散的（-1, 0, 1），不需要死区。
        但如果以后改用摇杆控制，就需要死区处理。
        """
        if abs(value) < self.deadzone:
            return 0.0
        return value

    def joy_callback(self, msg):
        """收到 /joy 回调函数。
        
        【处理流程】
        1. 读取手柄状态（hat_x, hat_y, RB）
        2. 判断操作模式（平移 vs 旋转）
        3. 计算速度值
        4. 发布 Twist 消息
        
        【手柄映射】
        平移模式（RB 未按下）：
        - D-pad 上 (hat_y=+1)  → 前进 (linear.x = +scale)
        - D-pad 下 (hat_y=-1)  → 后退 (linear.x = -scale)
        - D-pad 左 (hat_x=+1)  → 左平移 (linear.y = +scale)
        - D-pad 右 (hat_x=-1)  → 右平移 (linear.y = -scale)
        
        旋转模式（RB 按下）：
        - D-pad 左 (hat_x=+1)  → 逆时针旋转 (angular.z = +scale)
        - D-pad 右 (hat_x=-1)  → 顺时针旋转 (angular.z = -scale)
        
        【重要：SDL2 hat_x 极性】
        joy_node 使用 SDL2，其 hat_x 极性与 pygame 相反：
        - SDL2: 左 = +1, 右 = -1
        - pygame: 左 = -1, 右 = +1
        
        这个差异导致我们在第一次实现时搞反了方向。
        """
        twist = Twist()

        # 检查是否有 hat 数据（axes[6], axes[7]）
        # 标准 joy_node 输出 6 个 axes，加上 hat 后变成 8 个
        if len(msg.axes) >= 8:
            hat_x = msg.axes[6]  # D-pad 左右
            hat_y = msg.axes[7]  # D-pad 上下
            
            # RB 按钮（右肩键）
            # 检查 buttons 数组长度，避免 IndexError
            rb = msg.buttons[7] if len(msg.buttons) > 7 else 0

            # =================== 旋转模式 ===================
            if rb and hat_x > 0:
                # RB + 左 (hat_x=+1) = 逆时针旋转
                twist.angular.z = self.angular_scale
            elif rb and hat_x < 0:
                # RB + 右 (hat_x=-1) = 顺时针旋转
                twist.angular.z = -self.angular_scale
            
            # =================== 平移模式 ===================
            else:
                # 前进/后退
                if hat_y > 0:
                    twist.linear.x = self.linear_scale    # 前进
                elif hat_y < 0:
                    twist.linear.x = -self.linear_scale   # 后退
                
                # 左/右平移
                if hat_x > 0:
                    twist.linear.y = self.linear_scale    # 左平移
                elif hat_x < 0:
                    twist.linear.y = -self.linear_scale   # 右平移

        # 发布速度指令
        # 任何节点订阅了 /cmd_vel 都会收到这个消息
        self.pub.publish(twist)

        # 调试日志：仅在非零时打印，避免刷屏
        if twist.linear.x != 0 or twist.linear.y != 0 or twist.angular.z != 0:
            self.get_logger().info(
                f'cmd_vel: x={twist.linear.x:.2f}, '
                f'y={twist.linear.y:.2f}, '
                f'θ={twist.angular.z:.2f}'
            )


def main(args=None):
    """ROS2 节点入口函数。
    
    【标准模式】
    1. rclpy.init(): 初始化 ROS2
    2. 创建节点
    3. rclpy.spin(): 进入事件循环
    4. 清理资源
    
    【为什么不用 MultiThreadedExecutor？】
    这个节点只有一个回调（joy_callback），计算量很小，
    单线程 executor 完全足够。
    MultiThreadedExecutor 只在有多个耗时回调需要并行时才需要。
    """
    rclpy.init(args=args)
    node = JoyToCmdVel()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
