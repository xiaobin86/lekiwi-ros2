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

# 方式 A：仅底盘（无摄像头，响应最快）
python -m lekiwi_base.base_node

# 方式 B：底盘 + 摄像头（有轻微延迟）
python -m lekiwi_base.base_node --ros-args -p use_cameras:=true
```

### 2. 启动 PC 端（手柄控制）

开 **3 个终端**：

#### 终端 1：joy_node（手柄读取）
```powershell
cd D:\work\lerobot-workspace\lerobot-ros2
conda activate ros2
ros2 run joy joy_node
```

#### 终端 2：joy_to_cmd_vel（速度转换）
```powershell
cd D:\work\lerobot-workspace\lerobot-ros2\src\lekiwi_teleop
conda activate ros2
python -m lekiwi_teleop.joy_to_cmd_vel
```

#### 终端 3（可选）：查看速度指令
```powershell
cd D:\work\lerobot-workspace\lerobot-ros2\tools
conda activate ros2
python topic_monitor.py /cmd_vel
```

### 3. 查看摄像头图像（如果启用了摄像头）

```powershell
cd D:\work\lerobot-workspace\lerobot-ros2\tools
conda activate ros2

# front 摄像头
python image_viewer.py --ros-args -p topic:=/camera/front/image_raw

# wrist 摄像头
python image_viewer.py --ros-args -p topic:=/camera/wrist/image_raw
```

按 **Q** 退出图像窗口。

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
