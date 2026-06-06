# LeRobot-ROS2

基于 ROS2 的 LeKiwi 机器人控制与学习框架。

本项目将 LeRobot 硬件控制能力与 ROS2 通信框架结合，逐步构建一个可用于遥操作、视觉感知、导航与模仿学习的机器人系统。

## 硬件组成

- **LeKiwi 机器人**：三轮全向底盘 + SO101 从臂（运行在树莓派 5 上）
- **主臂**：SO101 Leader Arm（用于后续遥操作，Phase 1 暂不使用）
- **上位机**：Windows 11 + RTX 5070Ti Laptop
- **通信**：WiFi（ROS2 DDS）
- **手柄**：Alante Li Wireless Controller（非 Xbox，D-pad 控制）

## 阶段规划

| 阶段 | 目标 | 状态 |
|------|------|------|
| Phase 1 | 手柄遥控底盘移动 | ✅ 已完成 |
| Phase 2 | 加入摄像头、状态反馈、可视化 | ✅ 已完成 |
| Phase 3 | 机械臂遥操作 + 数据记录 | 🚧 待开发 |
| Phase 4 | 里程计 + SLAM + 导航 | 📋 规划中 |
| Phase 5 | 模仿学习 + 策略部署 | 📋 规划中 |

## 快速开始

```bash
# PC 端（Windows）
conda activate ros2
ros2 run joy joy_node
python -m lekiwi_teleop.joy_to_cmd_vel

# 树莓派端（Ubuntu）
python -m lekiwi_base.base_node

# PC 端查看图像（可选）
python tools/image_viewer.py --ros-args -p topic:=/camera/front/image_raw
```

详见 [QUICK_START.md](docs/QUICK_START.md)

## 文档

### 架构设计
- [Phase 1 架构设计](docs/architecture/phase1_chassis_teleop.md) - 底盘遥控
- [Phase 2 摄像头传输](docs/runbooks/phase2-camera-streaming.md) - 双摄像头 ROS2 传输

### 操作指南
- [环境安装指南](docs/architecture/installation-guide.md) - PC + 树莓派完整安装
- [快速启动指南](docs/QUICK_START.md) - 日常操作流程
- [Topic 调试技巧](docs/runbooks/topic-debugging.md) - 调试工具使用

### 项目结构

```
lerobot-ros2/
├── docs/                          # 文档
│   ├── architecture/              # 架构文档
│   ├── runbooks/                  # 操作手册
│   └── QUICK_START.md             # 快速启动
├── src/                           # ROS2 包
│   ├── lekiwi_teleop/             # PC 端遥操作
│   │   ├── lekiwi_teleop/
│   │   │   ├── joy_to_cmd_vel.py      # joy → cmd_vel 转换
│   │   │   └── image_viewer.py        # 摄像头图像显示
│   │   └── setup.py
│   ├── lekiwi_base/               # 树莓派端底盘驱动
│   │   ├── lekiwi_base/
│   │   │   └── base_node.py           # 底盘控制 + 摄像头
│   │   └── setup.py
│   └── lekiwi_bringup/            # Launch 文件
│       ├── launch/
│       │   ├── pc_teleop.launch.py    # PC端启动（手柄+可选摄像头）
│       │   └── pi_base.launch.py      # 树莓派端启动
├── tools/                         # 调试工具
│   ├── topic_monitor.py           # Topic 变化监视器
│   ├── test_gamepad.py            # 手柄硬件测试
│   └── image_viewer.py            # 图像查看器
└── README.md
```

## 核心特性

- ✅ **跨平台**：PC (Windows 11) ↔ 树莓派 (Ubuntu 24.04)
- ✅ **标准 ROS2**：使用 `geometry_msgs/Twist`、`sensor_msgs/Joy`、`sensor_msgs/Image`
- ✅ **双摄像头**：front (/dev/video2) + wrist (/dev/video0)，独立 Topic 发布
- ✅ **安全保护**：看门狗超时自动停车
- ✅ **调试友好**：变化检测监视器、手柄映射测试工具

## 许可证

Apache-2.0
