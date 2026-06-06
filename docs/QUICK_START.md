# 快速启动指南

## 日常操作流程

### 1. 启动树莓派端（底盘控制）

```bash
# SSH 到树莓派
ssh acelan@192.168.3.178
# 密码: 79480491

# 激活环境
cd ~/lerobot-workspace/lerobot-ros2
conda activate ros2

# 方式 A：一键启动（推荐）
# 仅底盘
ros2 launch lekiwi_bringup pi_base.launch.py

# 底盘 + 摄像头
ros2 launch lekiwi_bringup pi_base.launch.py use_cameras:=true

# 方式 B：手动启动（用于调试）
# 仅底盘
python -m lekiwi_base.base_node

# 底盘 + 摄像头
python -m lekiwi_base.base_node --ros-args -p use_cameras:=true
```

### 2. 启动 PC 端（手柄控制）

#### 方式 A：一键启动（推荐）

```powershell
cd D:\work\lerobot-workspace\lerobot-ros2
conda activate ros2
ros2 launch lekiwi_bringup pc_teleop.launch.py
```

这会同时启动：
- joy_node（手柄读取）
- joy_to_cmd_vel（速度转换）

#### 方式 B：手动启动（用于调试）

如果需要单独调试某个节点：

```powershell
# 终端 1：手柄读取
ros2 run joy joy_node

# 终端 2：速度转换（另一个终端）
python -m lekiwi_teleop.joy_to_cmd_vel

# 终端 3（可选）：查看速度输出
python tools/topic_monitor.py /cmd_vel
```

### 3. 查看摄像头图像（可选）

启动 PC 端时加上 `show_camera:=true`，会同时显示 front 和 wrist 两个摄像头：

```powershell
# 一键启动手柄 + 双摄像头显示
ros2 launch lekiwi_bringup pc_teleop.launch.py show_camera:=true

# 如果颜色偏蓝/红，禁用RGB转换
ros2 launch lekiwi_bringup pc_teleop.launch.py show_camera:=true convert_rgb:=false
```

按 **Q** 退出图像窗口。

> **注意**：树莓派端默认使用 JPEG 压缩传输图像（节省 70-90% WiFi 带宽）。如果图像质量不够，可在树莓派启动时禁用压缩：
> ```bash
> ros2 launch lekiwi_bringup pi_base.launch.py use_cameras:=true compress_images:=false
> ```

---

## 手柄操作

| 操作 | 按键 |
|------|------|
| 前进 | D-pad 上 |
| 后退 | D-pad 下 |
| 左平移 | D-pad 左 |
| 右平移 | D-pad 右 |
| 逆时针旋转 | RB + D-pad 左 |
| 顺时针旋转 | RB + D-pad 右 |

---

## 故障排查

### 底盘不动

1. 检查树莓派 `base_node` 是否运行
2. 检查 PC 和树莓派是否能互通：
   ```powershell
   ros2 topic list
   # 应该能看到 /cmd_vel
   ```
3. 检查手柄是否有输入：
   ```powershell
   python tools/topic_monitor.py /joy
   ```

### 摄像头不显示

1. 确认树莓派启动时加了 `-p use_cameras:=true`
2. 检查 Topic 是否存在：
   ```powershell
   ros2 topic list | findstr camera
   ```
3. 检查图像频率：
   ```powershell
   ros2 topic hz /camera/front/image_raw
   ```

### 底盘延迟

- 禁用摄像头：`python -m lekiwi_base.base_node`（不加 use_cameras）
- 摄像头读取会占用串口带宽，导致控制延迟

---

## 代码更新

当代码有更新时：

```bash
# 树莓派上
cd ~/lerobot-workspace/lerobot-ros2
git pull
cd src/lekiwi_base
pip install -e .

# PC 上
cd D:\work\lerobot-workspace\lerobot-ros2
git pull
cd src\lekiwi_teleop
pip install -e .
```
