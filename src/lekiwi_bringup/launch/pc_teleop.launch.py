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
    3. image_viewer_front (可选): 显示front摄像头
    4. image_viewer_wrist (可选): 显示wrist摄像头
    
    使用方法:
    # 基础启动（仅手柄+底盘控制）
    ros2 launch lekiwi_bringup pc_teleop.launch.py
    
    # 显示front摄像头（默认）
    ros2 launch lekiwi_bringup pc_teleop.launch.py show_camera:=true
    
    # 显示两个摄像头
    ros2 launch lekiwi_bringup pc_teleop.launch.py show_camera:=true show_wrist:=true
    
    # 如果颜色偏蓝/红，禁用RGB转换
    ros2 launch lekiwi_bringup pc_teleop.launch.py show_camera:=true convert_rgb:=false
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
            description='是否显示front摄像头 (true/false)'
        ),
        DeclareLaunchArgument(
            'show_wrist',
            default_value='false',
            description='是否显示wrist摄像头 (true/false)'
        ),
        DeclareLaunchArgument(
            'convert_rgb',
            default_value='true',
            description='BGR转RGB (默认true，如颜色偏则改为false)'
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

        # ========== 可选节点：front摄像头 ==========
        Node(
            package='lekiwi_teleop',
            executable=sys.executable,
            arguments=['-m', 'lekiwi_teleop.image_viewer'],
            name='image_viewer_front',
            parameters=[{
                'topic': '/camera/front/image_raw',
                'window_name': 'Front Camera',
                'convert_rgb': LaunchConfiguration('convert_rgb'),
            }],
            output='screen',
            condition=IfCondition(
                PythonExpression(["'", LaunchConfiguration('show_camera'), "' == 'true'"])
            ),
        ),

        # ========== 可选节点：wrist摄像头 ==========
        Node(
            package='lekiwi_teleop',
            executable=sys.executable,
            arguments=['-m', 'lekiwi_teleop.image_viewer'],
            name='image_viewer_wrist',
            parameters=[{
                'topic': '/camera/wrist/image_raw',
                'window_name': 'Wrist Camera',
                'convert_rgb': LaunchConfiguration('convert_rgb'),
            }],
            output='screen',
            condition=IfCondition(
                PythonExpression(["'", LaunchConfiguration('show_wrist'), "' == 'true'"])
            ),
        ),
    ])
