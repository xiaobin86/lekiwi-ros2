#!/usr/bin/env python3
"""ROS2 图像查看器：订阅 /camera/image_raw，用 OpenCV 显示。

轻量级替代 rqt_image_view，不需要额外依赖。
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2


class ImageViewer(Node):
    def __init__(self):
        super().__init__('image_viewer')

        self.declare_parameter('topic', '/camera/image_raw')
        self.declare_parameter('window_name', 'LeKiwi Camera')
        self.declare_parameter('convert_rgb', False)  # BGR→RGB 转换

        topic = self.get_parameter('topic').value
        self.window_name = self.get_parameter('window_name').value
        self.convert_rgb = self.get_parameter('convert_rgb').value

        self.sub = self.create_subscription(Image, topic, self.image_callback, 10)
        self.bridge = CvBridge()

        self.get_logger().info(f'图像查看器已启动，订阅: {topic}')
        if self.convert_rgb:
            self.get_logger().info('颜色转换: BGR → RGB')
        self.get_logger().info('按 Q 键退出')

    def image_callback(self, msg):
        try:
            # ROS2 Image → OpenCV
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

            # 如果需要，转换 BGR → RGB
            if self.convert_rgb:
                cv_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)

            # 显示图像
            cv2.imshow(self.window_name, cv_image)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.get_logger().info('收到退出信号')
                rclpy.shutdown()

        except Exception as e:
            self.get_logger().error(f'图像处理失败: {e}')

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
