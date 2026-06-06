from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node
import sys


def generate_launch_description():
    """PC端启动：手柄遥操作。
    
    启动节点：
    1. joy_node (ROS2官方): 读取手柄，发布 /joy
    2. joy_to_cmd_vel (自定义): 订阅 /joy，转换为 /cmd_vel
    3. image_viewer (可选): 显示摄像头图像
    
    使用方法:
    # 基础启动（仅手柄+底盘控制）
    ros2 launch lekiwi_bringup pc_teleop.launch.py
    
    # 带摄像头显示
    ros2 launch lekiwi_bringup pc_teleop.launch.py show_camera:=true
    
    # 指定摄像头话题
    ros2 launch lekiwi_bringup pc_teleop.launch.py show_camera:=true camera_topic:=/camera/wrist/image_raw
    """

    return LaunchDescription([
        # ========== 参数声明 ==========
        DeclareLaunchArgument(
            'linear_scale',
            default_value='0.5',
            description='线速度缩放 (m/s)'
        ),
        DeclareLaunchArgument(
            'angular_scale',
            default_value='1.0',
            description='角速度缩放 (rad/s)'
        ),
        DeclareLaunchArgument(
            'show_camera',
            default_value='false',
            description='是否显示摄像头图像 (true/false)'
        ),
        DeclareLaunchArgument(
            'camera_topic',
            default_value='/camera/front/image_raw',
            description='摄像头图像话题'
        ),
        DeclareLaunchArgument(
            'convert_rgb',
            default_value='false',
            description='BGR转RGB (如果颜色偏蓝/红则设为true)'
        ),

        # ========== 核心节点 ==========
        # joy_node: ROS2官方手柄节点
        Node(
            package='joy',
            executable='joy_node',
            name='joy_node',
            output='screen',
        ),

        # joy_to_cmd_vel: 将/joy转换为/cmd_vel
        Node(
            package='lekiwi_teleop',
            executable=sys.executable,
            arguments=['-m', 'lekiwi_teleop.joy_to_cmd_vel'],
            name='joy_to_cmd_vel',
            parameters=[{
                'linear_scale': LaunchConfiguration('linear_scale'),
                'angular_scale': LaunchConfiguration('angular_scale'),
            }],
            output='screen',
        ),

        # ========== 可选节点 ==========
        # image_viewer: 显示摄像头图像（仅在show_camera:=true时启动）
        # 使用 sys.executable 直接运行 Python 模块（避免需要重新安装包注册 entry_point）
        Node(
            package='lekiwi_teleop',
            executable=sys.executable,
            arguments=['-m', 'lekiwi_teleop.image_viewer'],
            name='image_viewer',
            parameters=[{
                'topic': LaunchConfiguration('camera_topic'),
                'convert_rgb': LaunchConfiguration('convert_rgb'),
            }],
            output='screen',
            condition=IfCondition(
                PythonExpression(["'", LaunchConfiguration('show_camera'), "' == 'true'"])
            ),
        ),
    ])
