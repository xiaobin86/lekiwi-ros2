#!/usr/bin/env python3
"""ROS2 图像查看器：订阅图像话题，用 OpenCV 显示。

支持两种格式：
- sensor_msgs/Image (未压缩)
- sensor_msgs/CompressedImage (JPEG压缩)

轻量级替代 rqt_image_view，不需要额外依赖。
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CompressedImage
from cv_bridge import CvBridge
import cv2
import numpy as np


class ImageViewer(Node):
    def __init__(self):
        super().__init__('image_viewer')

        self.declare_parameter('topic', '/camera/image_raw')
        self.declare_parameter('window_name', 'LeKiwi Camera')
        self.declare_parameter('convert_rgb', False)  # BGR→RGB 转换

        topic = self.get_parameter('topic').value
        self.window_name = self.get_parameter('window_name').value
        self.convert_rgb = self.get_parameter('convert_rgb').value

        # 自动检测话题类型：compressed 或 raw
        if '/compressed' in topic:
            self.sub = self.create_subscription(
                CompressedImage, topic, self.compressed_callback, 10
            )
        else:
            self.sub = self.create_subscription(
                Image, topic, self.image_callback, 10
            )
        
        self.bridge = CvBridge()

        self.get_logger().info(f'图像查看器已启动，订阅: {topic}')
        if self.convert_rgb:
            self.get_logger().info('颜色转换: BGR → RGB')
        self.get_logger().info('按 Q 键退出')

    def _display(self, cv_image):
        """显示图像（通用处理）。"""
        if self.convert_rgb:
            cv_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)

        cv2.imshow(self.window_name, cv_image)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            self.get_logger().info('收到退出信号')
            rclpy.shutdown()

    def image_callback(self, msg):
        """接收未压缩图像。"""
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            self._display(cv_image)
        except Exception as e:
            self.get_logger().error(f'图像处理失败: {e}')

    def compressed_callback(self, msg):
        """接收压缩图像（JPEG）。"""
        try:
            # 将 bytes 转换为 numpy array
            np_arr = np.frombuffer(msg.data, np.uint8)
            # JPEG 解码
            cv_image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            
            if cv_image is not None:
                self._display(cv_image)
            else:
                self.get_logger().warning('JPEG 解码失败')
        except Exception as e:
            self.get_logger().error(f'压缩图像处理失败: {e}')

    def destroy_node(self):
        cv2.destroyAllWindows()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ImageViewer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
