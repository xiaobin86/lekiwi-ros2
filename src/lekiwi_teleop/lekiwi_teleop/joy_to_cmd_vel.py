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

        # 完全按照 client_pc.py 的逻辑映射
        # joy_node 输出: axes[6]=hat_x (左=-1, 右=1), axes[7]=hat_y (上=1, 下=-1)
        # RB = buttons[7]
        if len(msg.axes) >= 8:
            hat_x = msg.axes[6]
            hat_y = msg.axes[7]
            rb = msg.buttons[7] if len(msg.buttons) > 7 else 0

            if rb and hat_x < 0:
                # RB + 左 = 逆时针旋转
                twist.angular.z = self.angular_scale
            elif rb and hat_x > 0:
                # RB + 右 = 顺时针旋转
                twist.angular.z = -self.angular_scale
            else:
                # D-pad 控制平移 (完全按照 client_pc.py)
                if hat_y > 0:
                    twist.linear.x = self.linear_scale
                elif hat_y < 0:
                    twist.linear.x = -self.linear_scale

                if hat_x < 0:
                    twist.linear.y = self.linear_scale
                elif hat_x > 0:
                    twist.linear.y = -self.linear_scale

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
