#!/usr/bin/env python3
"""简单的 joy → cmd_vel 转换节点，用于本地测试手柄映射。"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from geometry_msgs.msg import Twist


class JoyToCmdVel(Node):
    def __init__(self):
        super().__init__('joy_to_cmd_vel')

        self.sub = self.create_subscription(Joy, '/joy', self.joy_callback, 10)
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)

        # 参数（可调）
        self.declare_parameter('linear_scale', 0.5)   # 线速度缩放
        self.declare_parameter('angular_scale', 1.0)  # 角速度缩放
        self.declare_parameter('deadzone', 0.1)       # 死区

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
        if abs(value) < self.deadzone:
            return 0.0
        return value

    def joy_callback(self, msg):
        twist = Twist()

        # 映射（根据你的 Alante Li 手柄）：
        # axes[6] = D-pad 左右 (-1=左, 1=右)
        # axes[7] = D-pad 上下 (1=上, -1=下)
        # 但 client_pc.py 用的是 hat，这里 joy 消息里 hat 已经追加到 axes 末尾
        # axes[6] = hat_x, axes[7] = hat_y

        if len(msg.axes) >= 8:
            # 使用 hat (axes[6], axes[7])
            hat_x = self.apply_deadzone(msg.axes[6])   # 左右
            hat_y = self.apply_deadzone(msg.axes[7])   # 上下

            # 前/后
            twist.linear.x = hat_y * self.linear_scale
            # 左/右平移（全向底盘）
            twist.linear.y = -hat_x * self.linear_scale

            # 旋转：用 Button RB (buttons[7]) + 左右
            if len(msg.buttons) > 7 and msg.buttons[7] == 1:
                twist.angular.z = -hat_x * self.angular_scale
                # 旋转时清空平移
                twist.linear.x = 0.0
                twist.linear.y = 0.0

        self.pub.publish(twist)

        # 调试：仅在非零时打印
        if twist.linear.x != 0 or twist.linear.y != 0 or twist.angular.z != 0:
            self.get_logger().info(
                f'cmd_vel: x={twist.linear.x:.2f}, '
                f'y={twist.linear.y:.2f}, '
                f'θ={twist.angular.z:.2f}'
            )


def main(args=None):
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
