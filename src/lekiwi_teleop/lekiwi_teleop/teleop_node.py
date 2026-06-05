#!/usr/bin/env python3
"""PC端遥操作节点：将手柄Joy消息映射为底盘速度指令。"""

import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Joy


class LekiwiTeleopNode(Node):
    """手柄遥操作节点。
    
    订阅 /joy (game_controller_node 输出)，按 LeKiwi 键位规则映射为速度指令，
    发布 /cmd_vel。
    """

    def __init__(self):
        super().__init__('lekiwi_teleop_node')

        # 声明参数
        self.declare_parameter('max_linear_speed', 0.5)
        self.declare_parameter('max_angular_speed', 90.0)
        self.declare_parameter('speed_levels', [0.1, 0.3, 0.5])
        self.declare_parameter('publish_rate', 20.0)
        self.declare_parameter('dpad_mode', 'auto')  # 'auto', 'buttons', 'axes'

        # 读取参数
        self.max_linear_speed = self.get_parameter('max_linear_speed').value
        self.max_angular_speed = self.get_parameter('max_angular_speed').value
        self.speed_levels = self.get_parameter('speed_levels').value
        publish_rate = self.get_parameter('publish_rate').value
        self.dpad_mode = self.get_parameter('dpad_mode').value

        # 状态
        self.speed_index = 1  # 默认中速
        self.prev_lb = False
        self.exit_pressed = False
        self._joy_initialized = False

        # 发布 /cmd_vel
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)

        # 订阅 /joy
        self.joy_sub = self.create_subscription(
            Joy, '/joy', self.joy_callback, 10
        )

        # 定时发布（确保无输入时也发零速度）
        self.twist = Twist()
        self.timer = self.create_timer(1.0 / publish_rate, self.timer_callback)

        self.get_logger().info(
            'LekiwiTeleopNode started. '
            f'Speed levels: {self.speed_levels}. '
            'Waiting for /joy...'
        )

    def joy_callback(self, msg: Joy):
        """处理 Joy 消息，更新速度指令。
        
        支持两种 D-pad 模式：
        - buttons: game_controller_node，D-pad 是 buttons[11-14]
        - axes: joy_node，D-pad 是 hat axes（通常在 axes 末尾）
        """
        buttons = msg.buttons
        axes = msg.axes

        # 首次收到消息时打印结构，帮助调试
        if not self._joy_initialized:
            self._joy_initialized = True
            self.get_logger().info(
                f'Joy device: {len(axes)} axes, {len(buttons)} buttons. '
                f'D-pad mode: {self.dpad_mode}'
            )

        # 自动检测 D-pad 模式
        if self.dpad_mode == 'auto':
            # 如果有 8+ axes，假设最后两个是 hat (D-pad)
            if len(axes) >= 8:
                self.dpad_mode = 'axes'
                self.get_logger().info('Auto-detected D-pad mode: axes (hat)')
            else:
                self.dpad_mode = 'buttons'
                self.get_logger().info('Auto-detected D-pad mode: buttons')

        # START 退出 (button 7 通常是 Start/Menu)
        start_btn = 7 if len(buttons) > 7 else (6 if len(buttons) > 6 else -1)
        if start_btn >= 0 and buttons[start_btn] == 1:
            self.exit_pressed = True
            self.get_logger().info('START pressed, shutting down...')
            return

        # LB 切换速度档（button 4 通常是 LB/L1）
        lb_btn = 4 if len(buttons) > 4 else -1
        if lb_btn >= 0:
            lb_current = buttons[lb_btn] == 1
            if lb_current and not self.prev_lb:
                self.speed_index = (self.speed_index + 1) % len(self.speed_levels)
                names = ['Slow', 'Medium', 'Fast']
                self.get_logger().info(
                    f'Speed: {names[self.speed_index]} '
                    f'(xy={self.speed_levels[self.speed_index]})'
                )
            self.prev_lb = lb_current

        speed = self.speed_levels[self.speed_index]

        # RB (button 5 通常是 RB/R1)
        rb_btn = 5 if len(buttons) > 5 else -1
        rb_pressed = buttons[rb_btn] == 1 if rb_btn >= 0 else False

        # D-pad 读取
        dpad_up = False
        dpad_down = False
        dpad_left = False
        dpad_right = False

        if self.dpad_mode == 'axes' and len(axes) >= 8:
            # joy_node: D-pad 是 hat axes（最后两个）
            # axes[-2] = hat_x, axes[-1] = hat_y
            hat_x = axes[-2]
            hat_y = axes[-1]
            dpad_left = hat_x < -0.5
            dpad_right = hat_x > 0.5
            dpad_up = hat_y > 0.5
            dpad_down = hat_y < -0.5
        elif len(buttons) >= 15:
            # game_controller_node: D-pad 是 buttons[11-14]
            dpad_up = buttons[11] == 1
            dpad_down = buttons[12] == 1
            dpad_left = buttons[13] == 1
            dpad_right = buttons[14] == 1
        elif len(buttons) >= 12:
            # 某些手柄 D-pad 在 buttons[8-11]
            dpad_up = buttons[8] == 1
            dpad_down = buttons[9] == 1
            dpad_left = buttons[10] == 1
            dpad_right = buttons[11] == 1

        twist = Twist()

        if rb_pressed:
            # RB + 左/右 = 原地旋转
            if dpad_left:
                twist.angular.z = math.radians(self.max_angular_speed)
            elif dpad_right:
                twist.angular.z = -math.radians(self.max_angular_speed)
        else:
            # 平移控制
            if dpad_up:
                twist.linear.x = speed
            elif dpad_down:
                twist.linear.x = -speed

            if dpad_left:
                twist.linear.y = speed
            elif dpad_right:
                twist.linear.y = -speed

        self.twist = twist

    def timer_callback(self):
        """定时发布速度指令。"""
        if self.exit_pressed:
            # 发送零速度后退出
            self.cmd_pub.publish(Twist())
            self.get_logger().info('Published zero velocity, exiting...')
            rclpy.shutdown()
            return

        self.cmd_pub.publish(self.twist)


def main(args=None):
    rclpy.init(args=args)
    node = LekiwiTeleopNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # 退出前发零速度
        node.cmd_pub.publish(Twist())
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
