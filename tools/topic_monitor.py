#!/usr/bin/env python3
"""ROS2 Topic 监视器 - 只打印变化，不刷屏。"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from geometry_msgs.msg import Twist


class TopicMonitor(Node):
    def __init__(self, topic_name='/joy'):
        super().__init__('topic_monitor')
        self.topic_name = topic_name
        
        if topic_name == '/joy':
            self.sub = self.create_subscription(Joy, topic_name, self.joy_callback, 10)
        elif topic_name == '/cmd_vel':
            self.sub = self.create_subscription(Twist, topic_name, self.cmd_vel_callback, 10)
        else:
            self.get_logger().error(f'不支持的 topic: {topic_name}')
            return
            
        self.get_logger().info(f'监视 {topic_name} - 只显示变化')
        
        # 上一次状态
        self.prev_axes = None
        self.prev_buttons = None
        self.prev_twist = None
        
    def joy_callback(self, msg):
        changed = False
        
        # 检查按钮变化
        if self.prev_buttons is not None:
            for i, (prev, curr) in enumerate(zip(self.prev_buttons, msg.buttons)):
                if prev != curr:
                    action = "按下" if curr == 1 else "释放"
                    print(f"[Button {i}] {action}")
                    changed = True
        
        # 检查轴变化（阈值 0.1）
        if self.prev_axes is not None:
            for i, (prev, curr) in enumerate(zip(self.prev_axes, msg.axes)):
                if abs(prev - curr) > 0.1:
                    print(f"[Axis {i}] {curr:.3f}")
                    changed = True
        
        self.prev_axes = list(msg.axes)
        self.prev_buttons = list(msg.buttons)
    
    def cmd_vel_callback(self, msg):
        if self.prev_twist is not None:
            dx = abs(msg.linear.x - self.prev_twist.linear.x)
            dy = abs(msg.linear.y - self.prev_twist.linear.y)
            dz = abs(msg.angular.z - self.prev_twist.angular.z)
            
            if dx > 0.01 or dy > 0.01 or dz > 0.01:
                print(f"cmd_vel: x={msg.linear.x:.2f}, y={msg.linear.y:.2f}, θ={msg.angular.z:.2f}")
        
        self.prev_twist = msg


def main(args=None):
    import sys
    topic = sys.argv[1] if len(sys.argv) > 1 else '/joy'
    
    rclpy.init(args=args)
    node = TopicMonitor(topic)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
