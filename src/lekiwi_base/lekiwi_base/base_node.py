#!/usr/bin/env python3
"""树莓派端底盘驱动节点：接收 /cmd_vel，调用 LeRobot 驱动底盘。"""

import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


class LekiwiBaseNode(Node):
    """LeKiwi 底盘驱动节点。
    
    订阅 /cmd_vel，转换为 LeRobot action 格式，驱动底盘运动。
    包含看门狗安全保护。
    """

    def __init__(self):
        super().__init__('lekiwi_base_node')

        # 声明参数
        self.declare_parameter('port', '/dev/ttyACM0')
        self.declare_parameter('robot_id', 'lekiwi')
        self.declare_parameter('watchdog_timeout_ms', 500)
        self.declare_parameter('control_freq', 30.0)
        self.declare_parameter('use_cameras', False)

        # 读取参数
        port = self.get_parameter('port').value
        robot_id = self.get_parameter('robot_id').value
        self.watchdog_timeout_ms = self.get_parameter('watchdog_timeout_ms').value
        self.use_cameras = self.get_parameter('use_cameras').value

        # 初始化 LeRobot
        self._init_lerobot(port, robot_id)

        # 订阅 /cmd_vel
        self.cmd_sub = self.create_subscription(
            Twist, '/cmd_vel', self.cmd_vel_callback, 10
        )

        # 看门狗定时器
        self.last_cmd_time = self.get_clock().now()
        watchdog_period = self.watchdog_timeout_ms / 1000.0 / 2.0  # 检查频率为超时时间的一半
        self.watchdog_timer = self.create_timer(watchdog_period, self.watchdog_callback)

        # 控制循环定时器
        control_period = 1.0 / self.get_parameter('control_freq').value
        self.control_timer = self.create_timer(control_period, self.control_callback)

        # 当前动作缓存
        self.current_action = self._make_zero_action()
        self.action_lock = False  # 简单的动作锁

        self.get_logger().info(
            f'LekiwiBaseNode started. '
            f'Port: {port}, Watchdog: {self.watchdog_timeout_ms}ms, '
            f'Cameras: {self.use_cameras}'
        )

    def _init_lerobot(self, port: str, robot_id: str):
        """初始化 LeRobot LeKiwi。"""
        try:
            from lerobot.robots.lekiwi import LeKiwi
            from lerobot.robots.lekiwi.config_lekiwi import LeKiwiConfig
        except ImportError as e:
            self.get_logger().fatal(f'Failed to import LeRobot: {e}')
            raise

        try:
            config = LeKiwiConfig(port=port, id=robot_id)
            if not self.use_cameras:
                config.cameras = {}  # Phase 1 禁用摄像头

            self.robot = LeKiwi(config)
            self.robot.connect()
            self.get_logger().info('LeKiwi connected successfully')
        except Exception as e:
            self.get_logger().fatal(f'Failed to connect LeKiwi: {e}')
            raise

    ARM_DEFAULTS = {
        "arm_shoulder_pan.pos": 0.0,
        "arm_shoulder_lift.pos": -100.0,
        "arm_elbow_flex.pos": 90.0,
        "arm_wrist_flex.pos": 70.0,
        "arm_wrist_roll.pos": 0.0,
        "arm_gripper.pos": 0.0,
    }

    def _make_zero_action(self) -> dict:
        """创建零动作字典（停止底盘运动，但保持机械臂默认姿态）。"""
        action = dict(self.ARM_DEFAULTS)  # 复制默认机械臂姿态
        action.update({
            "x.vel": 0.0,
            "y.vel": 0.0,
            "theta.vel": 0.0,
        })
        return action

    def cmd_vel_callback(self, msg: Twist):
        """收到 /cmd_vel，转换为 LeRobot action 格式。"""
        # Twist.angular.z 是 rad/s，LeRobot 需要 deg/s
        action = self._make_zero_action()
        action["x.vel"] = msg.linear.x           # m/s
        action["y.vel"] = msg.linear.y           # m/s
        action["theta.vel"] = math.degrees(msg.angular.z)  # deg/s

        self.current_action = action
        self.last_cmd_time = self.get_clock().now()

    def control_callback(self):
        """定时向底盘发送动作指令。"""
        try:
            self.robot.send_action(self.current_action)
        except Exception as e:
            self.get_logger().error(f'Failed to send action: {e}')

    def watchdog_callback(self):
        """看门狗：超时未收到指令则停止底盘。"""
        now = self.get_clock().now()
        timeout = rclpy.duration.Duration(
            seconds=self.watchdog_timeout_ms / 1000.0
        )

        if now - self.last_cmd_time > timeout:
            # 超时，停止底盘
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
        """清理资源。"""
        self.get_logger().info('Shutting down, stopping base...')
        try:
            self.robot.stop_base()
            self.robot.disconnect()
        except Exception as e:
            self.get_logger().error(f'Error during shutdown: {e}')
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = LekiwiBaseNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
