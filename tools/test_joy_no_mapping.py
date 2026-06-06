#!/usr/bin/env python3
"""测试 joy_node 是否需要 SDL_GAMECONTROLLERCONFIG"""

import os
import subprocess
import sys

def test_joy_node_without_mapping():
    print("测试 joy_node 不设置 SDL_GAMECONTROLLERCONFIG...")
    print()
    
    # 清除环境变量
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

if __name__ == '__main__':
    test_joy_node_without_mapping()
