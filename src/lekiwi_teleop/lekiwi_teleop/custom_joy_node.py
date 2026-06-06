#!/usr/bin/env python3
"""使用 pygame 的自定义 Joy 节点，绕过 SDL2 兼容性问题。

参考 client_pc.py 的按钮映射:
  A=0, B=1, X=3, Y=4, LB=6, RB=7, BACK=10, START=11
D-pad 通过 get_hat(0) 读取，不是 axis。
"""

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

        # 等待手柄连接
        retry = 0
        while pygame.joystick.get_count() == 0 and retry < 50:
            self.get_logger().info(f'Waiting for joystick... ({retry}/50)')
            import time
            time.sleep(0.1)
            pygame.joystick.init()
            retry += 1

        if pygame.joystick.get_count() == 0:
            self.get_logger().error('No joystick found!')
            raise RuntimeError('No joystick')

        self.joystick = pygame.joystick.Joystick(0)
        self.joystick.init()

        axes = self.joystick.get_numaxes()
        buttons = self.joystick.get_numbuttons()
        hats = self.joystick.get_numhats()
        self.get_logger().info(
            f'Opened: {self.joystick.get_name()} | '
            f'{axes} axes, {buttons} buttons, {hats} hats'
        )

        # 打印一次初始状态用于调试
        self._print_initial_state()

    def _print_initial_state(self):
        """打印初始按钮/轴状态，帮助调试映射。"""
        pygame.event.pump()
        axes = [float(self.joystick.get_axis(i))
                for i in range(self.joystick.get_numaxes())]
        buttons = [int(self.joystick.get_button(i))
                   for i in range(self.joystick.get_numbuttons())]
        hats = [self.joystick.get_hat(i)
                for i in range(self.joystick.get_numhats())]
        self.get_logger().info(f'Initial axes: {axes}')
        self.get_logger().info(f'Initial buttons: {buttons}')
        self.get_logger().info(f'Initial hats: {hats}')

    def timer_callback(self):
        pygame.event.pump()

        msg = Joy()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'joy'

        # 读取 axes
        msg.axes = [float(self.joystick.get_axis(i))
                   for i in range(self.joystick.get_numaxes())]

        # 读取 buttons
        msg.buttons = [int(self.joystick.get_button(i))
                      for i in range(self.joystick.get_numbuttons())]

        # 读取 hats (D-pad) 并追加到 axes 末尾
        # hat 值: (-1,0)=左, (1,0)=右, (0,1)=上, (0,-1)=下, (0,0)=无
        for i in range(self.joystick.get_numhats()):
            hx, hy = self.joystick.get_hat(i)
            msg.axes.append(float(hx))
            msg.axes.append(float(hy))

        # 调试：检测变化并打印
        self._debug_input_changes(msg)

        self.pub.publish(msg)

    def _debug_input_changes(self, msg):
        """检测输入变化并打印到控制台，方便调试。"""
        # 初始化状态缓存
        if not hasattr(self, '_prev_axes'):
            self._prev_axes = list(msg.axes)
            self._prev_buttons = list(msg.buttons)
            return

        # 检查按钮变化
        for i, (prev, curr) in enumerate(zip(self._prev_buttons, msg.buttons)):
            if prev != curr:
                action = "按下" if curr == 1 else "释放"
                self.get_logger().info(f'[手柄] Button {i} {action}')

        # 检查轴变化（阈值 0.1）
        for i, (prev, curr) in enumerate(zip(self._prev_axes, msg.axes)):
            if abs(prev - curr) > 0.1:
                self.get_logger().info(f'[手柄] Axis {i}: {curr:.3f}')

        # 检查帽子变化（axes 最后两个是 hat）
        hat_start = len(self._prev_axes) - 2
        if hat_start >= 0:
            prev_hat = (self._prev_axes[hat_start], self._prev_axes[hat_start + 1])
            curr_hat = (msg.axes[hat_start], msg.axes[hat_start + 1])
            if prev_hat != curr_hat:
                self.get_logger().info(f'[手柄] Hat: {curr_hat}')

        self._prev_axes = list(msg.axes)
        self._prev_buttons = list(msg.buttons)


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
