#!/usr/bin/env python3
"""
自定义 Joy 节点：使用 pygame 读取手柄，发布 /joy 话题。

【ROS2 架构说明】
================
这是一个备用（fallback）手柄节点，当 ROS2 官方的 joy_node
无法识别手柄时使用。

【为什么需要这个节点？】
-------------------------
在某些情况下，ROS2 的 joy_node（基于 SDL2）可能无法正确读取手柄：
1. 手柄未被 SDL2 识别（缺少 gamecontrollerdb 映射）
2. Windows 上 SDL2 和 DirectInput 的兼容性问题
3. 特殊手柄（如国产手柄）没有标准映射

pygame 是另一个跨平台的游戏库，基于 SDL2，
但提供了更底层的 Joystick API（而非 Game Controller API），
可以读取任何被操作系统识别为游戏手柄的设备。

【与 joy_node 的区别】
----------------------
| 特性 | joy_node (ROS2) | custom_joy_node (pygame) |
|------|----------------|-------------------------|
| 底层库 | SDL2 Game Controller | SDL2 Joystick (via pygame) |
| 映射 | 固定 Xbox 布局 | 原始输入 |
| D-pad | axes (hat) | axes + hat |
| 兼容性 | 标准手柄 | 几乎所有手柄 |
| 稳定性 | 高 | 中 |

【当前项目中的使用】
--------------------
本项目使用 Alante Li 无线手柄，经测试 joy_node 可以正常工作，
所以 custom_joy_node 主要作为备用和调试工具。

【pygame 手柄 API】
-------------------
pygame.joystick 模块提供底层手柄访问：
- pygame.joystick.get_count(): 获取连接的手柄数量
- pygame.joystick.Joystick(id): 打开指定手柄
- joystick.get_axis(i): 读取第 i 个轴（-1.0 ~ 1.0）
- joystick.get_button(i): 读取第 i 个按钮（0 或 1）
- joystick.get_hat(i): 读取第 i 个帽子/D-pad（(-1,-1) ~ (1,1)）
- pygame.event.pump(): 更新手柄事件队列
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
import pygame


class CustomJoyNode(Node):
    """使用 pygame 的自定义 Joy 节点。
    
    【设计模式】
    这是一个"传感器驱动"节点：
    - 从硬件（手柄）读取数据
    - 转换为标准 ROS2 消息格式（sensor_msgs/Joy）
    - 发布到 /joy 话题
    
    【定时器 vs 事件驱动】
    我们使用定时器（50Hz）轮询手柄状态，而不是事件驱动。
    原因：
    1. ROS2 的发布频率需要稳定
    2. 轮询比事件处理更简单
    3. 50Hz 足够捕捉所有手柄输入（人最快按键约 10Hz）
    
    【Joy 消息格式】
    sensor_msgs/Joy:
    - header: 时间戳和坐标系
    - axes: float32[] - 模拟输入（摇杆、扳机、hat）
    - buttons: int32[] - 数字输入（按钮）
    
    注意：我们将 hat 值追加到 axes 数组末尾，
    这样订阅者可以通过 axes[-2], axes[-1] 获取 hat_x, hat_y。
    """

    def __init__(self):
        """节点构造函数。
        
        【初始化流程】
        1. 初始化 pygame（手柄库）
        2. 等待手柄连接（最多 5 秒）
        3. 打开手柄
        4. 创建发布者和定时器
        
        【重试机制】
        手柄可能需要几秒钟才能被操作系统识别。
        我们在循环中重试最多 50 次（每次 100ms，总共 5 秒）。
        """
        super().__init__('custom_joy_node')

        # 创建发布者：发布 /joy 话题
        self.pub = self.create_publisher(
            Joy,           # 消息类型
            '/joy',        # 话题名称（与 joy_node 兼容）
            10             # QoS 队列深度
        )
        
        # 创建定时器：每 20ms（50Hz）读取一次手柄
        # 50Hz 是常见的手柄轮询频率：
        # - 足够捕捉快速按键（人最快约 10Hz）
        # - 不会占用太多 CPU
        self.timer = self.create_timer(0.02, self.timer_callback)

        # ============================================================
        # 初始化 pygame 手柄
        # ============================================================
        pygame.init()           # 初始化 pygame 所有模块
        pygame.joystick.init()  # 初始化手柄子系统

        # 等待手柄连接
        retry = 0
        while pygame.joystick.get_count() == 0 and retry < 50:
            self.get_logger().info(f'Waiting for joystick... ({retry}/50)')
            import time
            time.sleep(0.1)  # 等待 100ms
            pygame.joystick.init()  # 重新初始化（某些系统需要）
            retry += 1

        # 检查是否找到手柄
        if pygame.joystick.get_count() == 0:
            self.get_logger().error('No joystick found!')
            raise RuntimeError('No joystick')

        # 打开第一个手柄（索引 0）
        self.joystick = pygame.joystick.Joystick(0)
        self.joystick.init()

        # 获取手柄信息
        axes = self.joystick.get_numaxes()
        buttons = self.joystick.get_numbuttons()
        hats = self.joystick.get_numhats()
        self.get_logger().info(
            f'Opened: {self.joystick.get_name()} | '
            f'{axes} axes, {buttons} buttons, {hats} hats'
        )

        # 打印初始状态（调试用）
        self._print_initial_state()

    def _print_initial_state(self):
        """打印初始状态，帮助调试手柄映射。
        
        【用途】
        启动时打印一次所有轴和按钮的初始值，
        帮助确认手柄是否被正确识别。
        
        【输出示例】
        Initial axes: [0.0, 0.0, 0.0, 0.0, -1.0, -1.0]
        Initial buttons: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        Initial hats: [(0, 0)]
        """
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
        """定时器回调：读取手柄状态并发布 /joy 消息。
        
        【执行流程】
        1. pygame.event.pump() - 更新手柄事件队列
        2. 读取所有轴、按钮、hat 的值
        3. 填充 Joy 消息
        4. 发布到 /joy
        
        【pygame.event.pump() 的作用】
        pygame 使用事件队列处理手柄输入。
        pump() 将底层 SDL2 的事件刷新到 pygame 的队列中。
        如果不调用 pump()，get_axis() 和 get_button() 可能返回旧值。
        
        【数据映射】
        pygame → ROS2 Joy:
        - get_axis(i) → axes[i]  (float, -1.0 ~ 1.0)
        - get_button(i) → buttons[i]  (int, 0 或 1)
        - get_hat(i) → axes.append(hat_x), axes.append(hat_y)
        
        hat 值是整数元组：
        - (-1, 0) = 左
        - (1, 0) = 右
        - (0, 1) = 上
        - (0, -1) = 下
        - (0, 0) = 无
        """
        pygame.event.pump()

        # 创建 Joy 消息
        msg = Joy()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'joy'

        # 读取所有轴（axes）
        # axes 数组长度 = 手柄的轴数量
        msg.axes = [float(self.joystick.get_axis(i))
                   for i in range(self.joystick.get_numaxes())]

        # 读取所有按钮
        # buttons 数组长度 = 手柄的按钮数量
        msg.buttons = [int(self.joystick.get_button(i))
                      for i in range(self.joystick.get_numbuttons())]

        # 读取 hat（D-pad）并追加到 axes 末尾
        # 这样 joy_to_cmd_vel 可以通过 axes[-2], axes[-1] 获取 hat 值
        # 与 joy_node 的输出格式保持一致
        for i in range(self.joystick.get_numhats()):
            hx, hy = self.joystick.get_hat(i)
            msg.axes.append(float(hx))
            msg.axes.append(float(hy))

        # 调试：检测输入变化并打印
        self._debug_input_changes(msg)

        # 发布消息
        self.pub.publish(msg)

    def _debug_input_changes(self, msg):
        """检测输入变化并打印，用于调试手柄映射。
        
        【实现原理】
        缓存上一次的状态（axes, buttons），
        每次比较新值和旧值，只在变化时打印。
        
        【用途】
        1. 确认手柄按键是否正确映射
        2. 测试新手柄的按键索引
        3. 调试 deadzone 设置
        
        【输出示例】
        [手柄] Button 0 按下
        [手柄] Axis 4: -0.969
        [手柄] Hat: (0.0, 1.0)
        """
        # 初始化状态缓存（第一次调用时）
        if not hasattr(self, '_prev_axes'):
            self._prev_axes = list(msg.axes)
            self._prev_buttons = list(msg.buttons)
            return

        # 检查按钮变化
        for i, (prev, curr) in enumerate(zip(self._prev_buttons, msg.buttons)):
            if prev != curr:
                action = "按下" if curr == 1 else "释放"
                self.get_logger().info(f'[手柄] Button {i} {action}')

        # 检查轴变化（使用阈值 0.1 避免抖动）
        for i, (prev, curr) in enumerate(zip(self._prev_axes, msg.axes)):
            if abs(prev - curr) > 0.1:
                self.get_logger().info(f'[手柄] Axis {i}: {curr:.3f}')

        # 检查 hat 变化（axes 最后两个是 hat）
        hat_start = len(self._prev_axes) - 2
        if hat_start >= 0:
            prev_hat = (self._prev_axes[hat_start], self._prev_axes[hat_start + 1])
            curr_hat = (msg.axes[hat_start], msg.axes[hat_start + 1])
            if prev_hat != curr_hat:
                self.get_logger().info(f'[手柄] Hat: {curr_hat}')

        # 更新缓存
        self._prev_axes = list(msg.axes)
        self._prev_buttons = list(msg.buttons)


def main(args=None):
    """ROS2 节点入口函数。"""
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
