# LeRobot-ROS2

基于 ROS2 的 LeKiwi 机器人控制与学习框架。

本项目将 LeRobot 硬件控制能力与 ROS2 通信框架结合，逐步构建一个可用于遥操作、视觉感知、导航与模仿学习的机器人系统。

## 硬件组成

- **LeKiwi 机器人**：三轮全向底盘 + SO101 从臂（运行在树莓派 5 上）
- **主臂**：SO101 Leader Arm（用于后续遥操作，Phase 1 暂不使用）
- **上位机**：Windows 11 + RTX 5070Ti Laptop
- **通信**：WiFi（ROS2 DDS）

## 阶段规划

| 阶段 | 目标 |
|------|------|
| Phase 1 | 手柄遥控底盘移动 |
| Phase 2 | 加入摄像头、状态反馈、可视化 |
| Phase 3 | 里程计 + SLAM |
| Phase 4 | 机械臂协同 + 模仿学习 |

## 文档

- [Phase 1 架构设计](docs/architecture/phase1_chassis_teleop.md)

## 许可证

Apache-2.0
