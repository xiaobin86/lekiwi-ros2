# Phase 1 编码前技术调研报告

> **调研日期**: 2026-06-05  
> **目的**: 在正式编码前，验证所有 API、依赖和跨平台问题的准确性，确保代码一次性通过。

---

## 1. ROS2 环境调研

### 1.1 Windows 11 支持状态 ⚠️

| 项目 | 结论 |
|------|------|
| 官方支持 | **Windows 11 不是 Tier 1 支持平台**。官方文档明确声明 ["Only Windows 10 is supported"](https://docs.ros.org/en/jazzy/Installation/Windows-Install-Binary.html) |
| 实际可行性 | 可通过 `pixi` + conda-forge 安装预编译二进制包，Windows 11 大概率能跑，但遇到问题没有官方保障 |
| Python 版本 | 由 pixi 环境决定，通常为 3.11 或 3.12 |
| 安装方式 | 下载 `ros2-jazzy-*-windows-release-amd64.zip` + `pixi.toml` |

**建议**：如果 Windows 11 安装遇到问题，PC 端可改用 **WSL2 Ubuntu 24.04** 运行 ROS2，手柄通过 USB/IP 或 Windows 端 joy 节点桥接。

### 1.2 树莓派 5 (ARM64) 支持状态 ✅

| 项目 | 结论 |
|------|------|
| 官方支持 | **Tier 1 支持**，可直接 `apt install ros-jazzy-desktop` |
| Python 版本 | Ubuntu 24.04 默认 Python 3.12，完全兼容 |
| 安装命令 | 见 [ROS2 Jazzy Raspberry Pi 安装指南](https://docs.ros.org/en/jazzy/How-To-Guides/Installing-on-Raspberry-Pi.html) |
| 内存建议 | 8GB RAM 足够，编译大型包时建议 `MAKEFLAGS=-j1` |

### 1.3 标准消息包导入 ✅

```python
from geometry_msgs.msg import Twist, Pose, Quaternion
from sensor_msgs.msg import Joy, Image, CameraInfo
from std_msgs.msg import Header
```

所有标准消息包在 `ros-jazzy-desktop` 中均已包含。

---

## 2. Joy / 手柄调研

### 2.1 关键发现：`joy_node` vs `game_controller_node`

ROS2 `joy` 包提供两个节点，行为**完全不同**：

| 特性 | `joy_node` | `game_controller_node`（推荐） |
|------|-----------|------------------------------|
| 底层 API | SDL2 Joystick API | SDL2 Game Controller API |
| 跨平台一致性 | ❌ **不一致** | ✅ **一致** |
| D-pad 映射 | 在 **axes 数组末尾**（每 hat 占 2 个 axes） | 在 **buttons 数组**（固定索引） |
| Xbox 手柄支持 | 依赖原生报告 | 使用 SDL2 内置 `gamecontrollerdb.txt` |

**GitHub Issue 证实**：`joy_node` 在 Windows 和 Linux 下映射不一致（[Issue #176](https://github.com/ros-drivers/joystick_drivers/issues/176)）。

### 2.2 `game_controller_node` 的 Xbox 固定索引

| Button Index | 功能 |
|-------------|------|
| 0 | A |
| 1 | B |
| 2 | X |
| 3 | Y |
| 4 | BACK |
| 5 | GUIDE |
| 6 | START |
| 7 | LEFT STICK |
| 8 | RIGHT STICK |
| 9 | LEFT SHOULDER (LB) |
| 10 | RIGHT SHOULDER (RB) |
| 11 | DPAD_UP |
| 12 | DPAD_DOWN |
| 13 | DPAD_LEFT |
| 14 | DPAD_RIGHT |

| Axis Index | 功能 |
|-----------|------|
| 0 | Left X |
| 1 | Left Y |
| 2 | Right X |
| 3 | Right Y |
| 4 | Left Trigger |
| 5 | Right Trigger |

**⚠️ 这意味着我们之前的键位映射需要调整！**

### 2.3 修正后的键位映射（使用 `game_controller_node`）

| 按键 | 原方案 (joy_node) | 修正后 (game_controller_node) |
|------|------------------|------------------------------|
| 前进 | `axes[7] < 0` | `buttons[11] == 1` (DPAD_UP) |
| 后退 | `axes[7] > 0` | `buttons[12] == 1` (DPAD_DOWN) |
| 左平移 | `axes[6] < 0` | `buttons[13] == 1` (DPAD_LEFT) |
| 右平移 | `axes[6] > 0` | `buttons[14] == 1` (DPAD_RIGHT) |
| 旋转 (RB+方向) | `buttons[7] + axes[6]` | `buttons[10] + buttons[13/14]` |
| 切换速度 (LB) | `buttons[6]` | `buttons[9]` |
| 退出 (START) | `buttons[11]` | `buttons[6]` |

### 2.4 建议方案

**Phase 1 使用 `game_controller_node`**，原因：
1. Xbox 手柄在 SDL2 数据库中，跨平台一致
2. 不需要处理 axes 索引差异
3. 按钮式 D-pad 更适合离散控制（不需要死区处理）

启动命令：
```bash
ros2 run joy game_controller_node --ros-args -p device_id:=0
```

---

## 3. LeRobot API 调研

### 3.1 已验证的导入路径 ✅

```python
from lerobot.robots.lekiwi import LeKiwi
from lerobot.robots.lekiwi.config_lekiwi import LeKiwiConfig
```

### 3.2 `send_action()` 的 action dict 格式 ⚠️

**必须包含所有 9 个键，没有默认值！** 缺失任意键会 `KeyError`。

```python
action = {
    "arm_shoulder_pan.pos":  0.0,   # 度，Phase 1 发送 0
    "arm_shoulder_lift.pos": 0.0,   # 度，Phase 1 发送 0
    "arm_elbow_flex.pos":    0.0,   # 度，Phase 1 发送 0
    "arm_wrist_flex.pos":    0.0,   # 度，Phase 1 发送 0
    "arm_wrist_roll.pos":    0.0,   # 度，Phase 1 发送 0
    "arm_gripper.pos":       0.0,   # 0-100，Phase 1 发送 0
    "x.vel":                 0.3,   # m/s
    "y.vel":                 0.0,   # m/s
    "theta.vel":             0.0,   # deg/s（注意：不是 rad/s！）
}
```

**单位确认**：
- `x.vel`, `y.vel`: **m/s** ✅
- `theta.vel`: **deg/s** ✅（不是 rad/s，ROS2 Twist 用 rad/s，base_node 中必须转换）

### 3.3 `get_observation()` 返回内容 ✅

```python
obs = robot.get_observation()
# obs["x.vel"]       -> float, m/s
# obs["y.vel"]       -> float, m/s
# obs["theta.vel"]   -> float, deg/s
```

### 3.4 串口权限 ✅

```bash
# 不需要 root，但需要 dialout 组
sudo usermod -a -G dialout $USER
# 重新登录生效
```

### 3.5 树莓派性能预估

| 组件 | CPU | RAM |
|------|-----|-----|
| LeRobot Host (30Hz + 摄像头) | 30-60% | 1-2 GB |
| ROS2 简单节点 (少量 topic) | 10-25% | 200-500 MB |
| 总计 | 40-85% | 1.5-2.5 GB |

**结论**：Pi 5 (8GB) 完全可以承受，但建议控制循环保持 30Hz，不要过高。

---

## 4. DDS 跨平台通信调研

### 4.1 默认实现 ✅

ROS2 Jazzy 默认使用 **Fast DDS** (`rmw_fastrtps_cpp`)，Windows 和 Linux 二进制包均已包含。

### 4.2 关键环境变量

| 变量 | 值 | 说明 |
|------|-----|------|
| `ROS_DOMAIN_ID` | 42 | 隔离不同 ROS2 网络（0-101 安全范围） |
| `ROS_AUTOMATIC_DISCOVERY_RANGE` | SUBNET | 控制发现范围 |

### 4.3 Windows 防火墙 ⚠️

**会阻止 DDS 通信！** 首次运行需允许 Python/ROS2 通过防火墙。

### 4.4 家庭 WiFi 路由器 ⚠️

部分路由器会阻止设备间多播，导致节点无法互相发现。

**排查命令**：
```bash
# 终端 A（树莓派）
ros2 multicast send

# 终端 B（PC）
ros2 multicast receive
# 如果收不到 → 多播被阻止，改用 ROS_STATIC_PEERS
```

### 4.5 性能 ✅

`/cmd_vel` 这类小消息（几十 bytes）在 WiFi 下延迟 **1-10ms**，10-50Hz 完全没问题。

---

## 5. 关键修正清单

基于调研结果，架构文档和后续代码需要以下修正：

| # | 问题 | 修正 |
|---|------|------|
| 1 | Windows 11 ROS2 支持 | 文档中注明"非官方支持，如遇问题可改用 WSL2" |
| 2 | Joy 节点选择 | 使用 `game_controller_node` 替代 `joy_node` |
| 3 | D-pad 映射 | 从 axes 改为 buttons（11-14） |
| 4 | LB/RB/START 索引 | 更新为 game_controller_node 的固定索引 |
| 5 | `send_action` 单位 | `theta.vel` 用 deg/s，base_node 中从 rad/s 转换 |
| 6 | action dict 完整性 | 必须包含所有 9 个键，机械臂部分补 0.0 |
| 7 | 防火墙提示 | 文档中增加 Windows 防火墙配置说明 |
| 8 | 多播排查 | 增加 `ros2 multicast` 调试命令 |

---

## 6. 建议的开发策略

1. **先验证环境**：在 PC 和树莓派上分别安装 ROS2 Jazzy，确认 `ros2 topic list` 能互相看到
2. **先跑通 joy**：PC 端先单独启动 `game_controller_node`，用 `ros2 topic echo /joy` 确认手柄映射
3. **再写 teleop_node**：基于确认后的 Joy 消息格式写速度映射
4. **最后写 base_node**：在树莓派上测试 LeRobot 连接和底盘运动

---

## 版本迭代记录

| 日期 | 操作 | 内容摘要 |
|------|------|---------|
| 2026-06-05 | 创建 | 基于并行子代理深度调研 ROS2、LeRobot、joy、DDS |
