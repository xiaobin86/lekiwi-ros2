#!/usr/bin/env python3
"""使用 pygame 的自定义 Joy 节点，绕过 SDL2 兼容性问题。"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
import pygame


class CustomJoyNode(Node):
    def __init__(self):
        super().__init__('custom_joy_node')

        self.pub = self.create_publisher(Joy, '/joy', 10)
        self.timer = self.create_timer(0.02, self.timer_callback)  # 50Hz

        pygame.init()
        pygame.joystick.init()

        if pygame.joystick.get_count() == 0:
            self.get_logger().error('No joystick found!')
            raise RuntimeError('No joystick')

        self.joystick = pygame.joystick.Joystick(0)
        self.joystick.init()

        axes = self.joystick.get_numaxes()
        buttons = self.joystick.get_numbuttons()
        self.get_logger().info(
            f'Opened: {self.joystick.get_name()} | '
            f'{axes} axes, {buttons} buttons'
        )

    def timer_callback(self):
        pygame.event.pump()

        msg = Joy()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'joy'

        msg.axes = [float(self.joystick.get_axis(i))
                   for i in range(self.joystick.get_numaxes())]
        msg.buttons = [int(self.joystick.get_button(i))
                      for i in range(self.joystick.get_numbuttons())]

        self.pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = CustomJoyNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
