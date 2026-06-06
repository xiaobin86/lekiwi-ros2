from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
import sys


def generate_launch_description():
    """PC端启动：手柄遥操作。"""

    return LaunchDescription([
        # 参数声明
        DeclareLaunchArgument(
            'max_linear_speed',
            default_value='0.5',
            description='最大线速度 (m/s)'
        ),
        DeclareLaunchArgument(
            'max_angular_speed',
            default_value='90.0',
            description='最大角速度 (deg/s)'
        ),
        DeclareLaunchArgument(
            'publish_rate',
            default_value='20.0',
            description='发布频率 (Hz)'
        ),

        # 自定义 joy 节点（使用 pygame，绕过 SDL2 兼容性问题）
        Node(
            package='lekiwi_teleop',
            executable=sys.executable,
            arguments=['-m', 'lekiwi_teleop.custom_joy_node'],
            name='custom_joy_node',
            output='screen',
        ),

        # lekiwi_teleop_node：手柄 → /cmd_vel
        Node(
            package='lekiwi_teleop',
            executable=sys.executable,
            arguments=['-m', 'lekiwi_teleop.teleop_node'],
            name='lekiwi_teleop_node',
            parameters=[{
                'max_linear_speed': LaunchConfiguration('max_linear_speed'),
                'max_angular_speed': LaunchConfiguration('max_angular_speed'),
                'speed_levels': [0.1, 0.3, 0.5],
                'publish_rate': LaunchConfiguration('publish_rate'),
            }],
            output='screen',
        ),
    ])
