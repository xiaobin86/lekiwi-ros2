#!/usr/bin/env python3
"""简单的 pygame 手柄测试工具 - 实时输出按键、轴和帽子状态"""

import pygame
import sys
import time

def main():
    pygame.init()
    pygame.joystick.init()
    
    print("=" * 60)
    print("手柄测试工具")
    print("=" * 60)
    
    # 等待手柄连接
    print("\n等待手柄连接...")
    retry = 0
    while pygame.joystick.get_count() == 0 and retry < 50:
        time.sleep(0.1)
        pygame.joystick.init()
        retry += 1
        print(f"  尝试 {retry}/50...")
    
    if pygame.joystick.get_count() == 0:
        print("❌ 未检测到手柄！")
        print("\n可能的原因：")
        print("1. 手柄未插入或未开启")
        print("2. 需要管理员权限运行终端")
        print("3. 手柄驱动问题")
        input("\n按 Enter 退出...")
        return
    
    # 打开手柄
    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    
    name = joystick.get_name()
    num_axes = joystick.get_numaxes()
    num_buttons = joystick.get_numbuttons()
    num_hats = joystick.get_numhats()
    
    print(f"\n✅ 检测到手柄: {name}")
    print(f"   轴数量: {num_axes}")
    print(f"   按钮数量: {num_buttons}")
    print(f"   帽子数量: {num_hats}")
    print("\n" + "=" * 60)
    print("开始监听手柄输入...")
    print("按 Ctrl+C 退出")
    print("=" * 60 + "\n")
    
    # 记录上一次状态，用于检测变化
    prev_axes = [0.0] * num_axes
    prev_buttons = [0] * num_buttons
    prev_hats = [(0, 0)] * num_hats
    
    try:
        while True:
            pygame.event.pump()
            
            # 检查按钮变化
            for i in range(num_buttons):
                state = joystick.get_button(i)
                if state != prev_buttons[i]:
                    if state == 1:
                        print(f"[按钮按下] Button {i}")
                    else:
                        print(f"[按钮释放] Button {i}")
                    prev_buttons[i] = state
            
            # 检查轴变化（阈值 0.1 避免抖动）
            for i in range(num_axes):
                value = joystick.get_axis(i)
                if abs(value - prev_axes[i]) > 0.1:
                    print(f"[轴变化] Axis {i}: {value:.3f}")
                    prev_axes[i] = value
            
            # 检查帽子变化
            for i in range(num_hats):
                value = joystick.get_hat(i)
                if value != prev_hats[i]:
                    print(f"[方向键] Hat {i}: {value}")
                    prev_hats[i] = value
            
            time.sleep(0.05)  # 20Hz 采样
            
    except KeyboardInterrupt:
        print("\n\n已退出")
    finally:
        pygame.quit()

if __name__ == '__main__':
    main()
