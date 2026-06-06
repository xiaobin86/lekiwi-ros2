#!/usr/bin/env python3
"""测试 joy_node 是否需要 SDL_GAMECONTROLLERCONFIG 映射文件。

【使用场景】
当手柄在 joy_node 中无法识别时，首先确认是否是映射文件问题。
Alante Li Wireless Controller 等第三方手柄可能没有内置 SDL 映射。

【测试方法】
1. 清除 SDL_GAMECONTROLLERCONFIG 环境变量（避免干扰）
2. 启动 joy_node（不加载任何映射文件）
3. 使用 topic_monitor.py 检查 /joy topic 是否有输出
4. 如果有输出 → 手柄原生支持，不需要映射文件
5. 如果无输出 → 需要映射文件或改用 game_controller_node

【历史背景】
在早期调研中，我们以为第三方手柄都需要 SDL_GAMECONTROLLERCONFIG。
实际测试发现 Alante Li 在 joy_node 中可以正常工作（作为 Joystick 而非 Game Controller）。

【结论】
本项目最终使用 joy_node（非 game_controller_node），因为：
- Alante Li 在 joy_node 中直接可用
- hat 映射为 axes[6]/axes[7]，符合直觉
- 不需要维护复杂的 SDL 映射文件
"""

import os
import subprocess
import sys

def test_joy_node_without_mapping():
    """测试不设置映射文件时 joy_node 是否能识别手柄。"""
    print("测试 joy_node 不设置 SDL_GAMECONTROLLERCONFIG...")
    print()
    
    # 清除环境变量
    # SDL_GAMECONTROLLERCONFIG 是 SDL2 用于识别手柄映射的环境变量
    # 如果设置了此变量，SDL2 会使用内置映射而非自动检测
    if 'SDL_GAMECONTROLLERCONFIG' in os.environ:
        del os.environ['SDL_GAMECONTROLLERCONFIG']
        print("✅ 已清除 SDL_GAMECONTROLLERCONFIG")
    else:
        print("ℹ️  环境变量未设置")
    
    print()
    print("请在另一个终端运行:")
    print("  ros2 run joy joy_node")
    print()
    print("然后在本终端运行监视器:")
    print("  python topic_monitor.py /joy")
    print()
    print("按手柄测试是否有输出...")
    print()
    print("【预期结果】")
    print("如果手柄有输出 → 可以直接使用 joy_node，不需要映射文件")
    print("如果手柄无输出 → 可能需要映射文件或改用 game_controller_node")

if __name__ == '__main__':
    test_joy_node_without_mapping()
