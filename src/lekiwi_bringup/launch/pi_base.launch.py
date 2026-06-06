from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
import sys


def generate_launch_description():
    """树莓派端启动：底盘驱动。"""

    return LaunchDescription([
        # 参数声明
        DeclareLaunchArgument(
            'port',
            default_value='/dev/ttyACM0',
            description='底盘串口设备'
        ),
        DeclareLaunchArgument(
            'robot_id',
            default_value='lekiwi',
            description='机器人ID'
        ),
        DeclareLaunchArgument(
            'watchdog_timeout_ms',
            default_value='500',
            description='看门狗超时时间 (ms)'
        ),
        DeclareLaunchArgument(
            'control_freq',
            default_value='30.0',
            description='控制频率 (Hz)'
        ),
        DeclareLaunchArgument(
            'use_cameras',
            default_value='false',
            description='是否启用摄像头'
        ),

        # lekiwi_base_node：/cmd_vel → 底盘
        Node(
            package='lekiwi_base',
            executable=sys.executable,
            arguments=['-m', 'lekiwi_base.base_node'],
            name='lekiwi_base_node',
            parameters=[{
                'port': LaunchConfiguration('port'),
                'watchdog_timeout_ms': LaunchConfiguration('watchdog_timeout_ms'),
                'control_freq': LaunchConfiguration('control_freq'),
                'use_cameras': LaunchConfiguration('use_cameras'),
            }],
            output='screen',
        ),
    ])
