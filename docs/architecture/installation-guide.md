# 环境安装指南

> **文档版本**: v1.0  
> **日期**: 2026-06-05  
> **环境名**: `ros2` (conda)  
> **ROS2 版本**: Jazzy Jalisco  

---

## 概述

本指南说明如何在 **PC (Windows 11)** 和 **树莓派 5 (Ubuntu 24.04 ARM64)** 上，使用 **conda** 创建名为 `ros2` 的独立环境，并安装 Phase 1 所需的所有依赖。

**为什么选择 conda？**
- 隔离性强，不影响系统 Python
- 便于管理不同项目的 ROS2 版本
- 跨平台统一体验（Windows/Linux 命令一致）

---

## 1. 前置条件

### 1.1 已安装的软件

| 平台 | 需要预装 |
|------|---------|
| Windows 11 | [Miniforge](https://github.com/conda-forge/miniforge/releases) 或 Anaconda/Miniconda |
| Ubuntu 24.04 (树莓派) | [Miniforge](https://github.com/conda-forge/miniforge/releases)（推荐）或 apt 安装的 conda |
| 双方 | Git、VS Code（可选） |

### 1.2 网络要求

- 能访问 `conda-forge` 和 `github.com`
- PC 和树莓派在同一 WiFi 局域网
- 如果访问外网慢，可配置国内镜像（见第 5 节）

---

## 2. PC 端安装（Windows 11）

> ⚠️ **注意**：ROS2 Jazzy 官方仅 Tier 1 支持 Windows 10。Windows 11 通过 conda-forge (robostack) 安装经社区验证可用，但非官方保障。如遇严重问题，可改用 WSL2 Ubuntu 24.04。

### 2.1 安装 Miniforge（如未安装）

```powershell
# 下载 Miniforge3 (Windows x86_64)
# https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Windows-x86_64.exe
# 运行安装程序，勾选 "Add to PATH"

# 验证安装
conda --version
```

### 2.2 创建 conda 环境

```powershell
# 创建环境（Python 3.11，与 ROS2 Jazzy 二进制包兼容）
conda create -n ros2 python=3.11 -y

# 激活环境
conda activate ros2

# 配置 conda-forge 渠道（robostack 依赖）
conda config --env --add channels conda-forge
conda config --env --add channels robostack-jazzy
conda config --env --set channel_priority strict
```

### 2.3 安装 ROS2 Jazzy

```powershell
# 安装 ROS2 Jazzy 桌面版
conda install ros-jazzy-desktop -y

# 安装常用工具
conda install colcon-common-extensions rosdep -y

# 初始化 rosdep（可选，conda 环境通常不需要）
# rosdep init
# rosdep update
```

### 2.4 安装 joy 包

```powershell
# game_controller_node 在 joy 包中
conda install ros-jazzy-joy -y

# 验证安装
ros2 run joy game_controller_node --help
```

### 2.5 配置 ROS2 环境变量自动加载

**重要**：conda 激活时不会自动 source ROS2 的 setup 文件，导致 `AMENT_PREFIX_PATH` 未设置，ROS2 命令报错。需要配置 PowerShell 的 activate hook。

```powershell
# 1. 确认在 ros2 环境
conda activate ros2

# 2. 创建 PowerShell activate hook
# 这个文件会在每次 conda activate ros2 时自动执行
$hookPath = "$env:CONDA_PREFIX\etc\conda\activate.d\ros2_setup.ps1"
New-Item -ItemType Directory -Path (Split-Path $hookPath) -Force

@"
# ROS2 AMENT_PREFIX_PATH（必须）
\$env:AMENT_PREFIX_PATH = "\$env:CONDA_PREFIX\Library"

# ROS2 网络隔离（推荐）
\$env:ROS_DOMAIN_ID = "42"
\$env:ROS_AUTOMATIC_DISCOVERY_RANGE = "SUBNET"
"@ | Set-Content $hookPath

# 3. 验证配置（退出再重新激活）
conda deactivate
conda activate ros2

# 检查环境变量
$env:AMENT_PREFIX_PATH
$env:ROS_DOMAIN_ID

# 测试 ROS2
ros2 --version
ros2 run joy game_controller_node --help
```

**为什么需要这一步？**
- conda 的 `activate.d` 只自动执行 `.ps1` 文件（PowerShell）
- ROS2 的 `local_setup.bat` 在 PowerShell 中通过 `&` 执行时，环境变量不会传回父进程
- 直接设置 `$env:AMENT_PREFIX_PATH` 是最可靠的方案

**activate.d hook vs Profile 函数**

| 方案 | 使用方式 | 推荐度 |
|------|---------|--------|
| **activate.d hook** | `conda activate ros2` 后自动设置 | ✅ 推荐 |
| Profile 函数 | 需额外执行 `ros2-env` | ⚠️ 容易遗忘 |

### 2.6 安装 cv_bridge（用于图像传输）

Phase 2 摄像头功能需要 `cv_bridge`：

```powershell
conda activate ros2
pip install cv-bridge
```

### 2.7 安装项目包

```powershell
cd D:\work\lerobot-workspace\lerobot-ros2

# 安装 PC 端遥操作包
pip install -e src/lekiwi_teleop/

# 验证
python -m lekiwi_teleop.joy_to_cmd_vel --help
```

### 2.8 安装开发依赖

```powershell
# 在 ros2 环境中安装 pip 包
pip install numpy pillow pyserial

# 安装 colcon（如果 conda 没有）
pip install colcon-common-extensions
```

### 2.7 验证安装

```powershell
# 激活环境
conda activate ros2

# 检查 ROS2 是否可用
ros2 --version

# 测试 talker/listener（开两个 PowerShell 窗口）
# 窗口 1
ros2 run demo_nodes_cpp talker
# 窗口 2
ros2 run demo_nodes_py listener
```

### 2.8 Windows 防火墙配置

首次运行 ROS2 节点时，Windows 会弹出防火墙提示：

1. 勾选 **专用网络** 和 **公用网络**
2. 点击 **允许访问**

如果之前拒绝了，手动添加规则：

```powershell
# 以管理员身份运行 PowerShell（以下命令需要管理员权限）

# 方法1：从开始菜单搜索 PowerShell，右键选择"以管理员身份运行"
# 方法2：按 Win+X，选择"终端(管理员)"
# 方法3：在当前 PowerShell 中执行：
Start-Process powershell -Verb runAs

# 允许 ping（树莓派 ping PC 需要）
New-NetFirewallRule -DisplayName "Allow Ping" -Direction Inbound -Protocol ICMPv4 -IcmpType 8 -Action Allow

# 允许 ROS2 程序通过防火墙
New-NetFirewallRule -DisplayName "ROS2" -Direction Inbound -Program "C:\Users\acela\.conda\envs\ros2\python.exe" -Action Allow

# 或者临时关闭防火墙（仅测试使用，测试后建议开启）
Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled False
# 测试完成后重新开启：
# Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled True
```

---

## 3. 树莓派端安装（Ubuntu 24.04 ARM64）

### 3.1 安装 Miniforge（如未安装）

```bash
# 下载 Miniforge3 (Linux aarch64)
curl -L -o Miniforge3.sh "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh"
bash Miniforge3.sh -b -p $HOME/miniforge3

# 初始化 shell
$HOME/miniforge3/bin/conda init bash

# 重新加载配置
source ~/.bashrc
```

### 3.2 创建 conda 环境

```bash
# 创建环境
conda create -n ros2 python=3.11 -y

# 激活环境
conda activate ros2

# 配置渠道
conda config --env --add channels conda-forge
conda config --env --add channels robostack-jazzy
conda config --env --set channel_priority strict
```

### 3.3 安装 ROS2 Jazzy

```bash
# 树莓派是 headless（无图形界面），安装 ros-base 即可
# ros-base 包含所有核心通信和机器人库，不含 RViz2 等 GUI 工具
conda install ros-jazzy-ros-base -y

# 安装工具
conda install colcon-common-extensions -y
```

> **为什么不用 desktop？**
> `desktop` 包含 RViz2、RQt 等 GUI 工具，会拉取 Qt、OpenGL 等大量图形依赖。树莓派无显示器，这些依赖完全用不上，只会浪费磁盘空间和安装时间。
>
> **为什么不装 joy？**
> 手柄在 PC 端读取，树莓派只接收 `/cmd_vel` 话题，不需要 joy 包。
>
> **注意**：ARM64 上某些包可能没有预编译二进制，需要编译。如果遇到 `PackagesNotFoundError`，尝试单线程安装或减少并发。

### 3.4 安装 LeRobot

LeRobot 不在 conda-forge 中，需要从源码安装到 conda 环境里：

```bash
# 确保在 ros2 环境中
conda activate ros2

# 进入 LeRobot 源码目录
cd ~/lerobot-workspace/lerobot

# 安装到当前 conda 环境
pip install -e ".[lekiwi]"

# 验证
python -c "from lerobot.robots.lekiwi import LeKiwi; print('LeRobot OK')"
```

### 3.5 安装其他依赖

```bash
# 在 ros2 环境中
conda activate ros2

pip install pyserial numpy pillow
```

### 3.6 串口权限配置

```bash
# 将当前用户加入 dialout 组（需要重新登录生效）
sudo usermod -aG dialout $USER

# 临时授权（立即生效，重启后失效）
sudo chmod 666 /dev/ttyACM0
```

### 3.7 配置 ROS2 环境变量自动加载

**重要**：conda 激活时不会自动 source ROS2 的 setup 文件。需要配置 bash 的 activate hook。

```bash
# 1. 确认在 ros2 环境
conda activate ros2

# 2. 创建 bash activate hook
mkdir -p $CONDA_PREFIX/etc/conda/activate.d
cat > $CONDA_PREFIX/etc/conda/activate.d/ros2_setup.sh << 'EOF'
export AMENT_PREFIX_PATH="$CONDA_PREFIX"
export ROS_DOMAIN_ID=42
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
EOF

# 3. 验证（退出再重新激活）
conda deactivate
conda activate ros2

echo $AMENT_PREFIX_PATH
echo $ROS_DOMAIN_ID
```

**⚠️ Linux 与 Windows 路径差异**：

| 平台 | AMENT_PREFIX_PATH | 说明 |
|------|-------------------|------|
| **Windows** | `$CONDA_PREFIX/Library` | 可执行文件在 `Library/bin/` |
| **Linux** | `$CONDA_PREFIX` | 可执行文件在 `lib/` |

### 3.8 验证安装

```bash
# 激活环境
conda activate ros2

# 检查 ROS2
ros2 --version

# 测试话题系统
ros2 topic list

# 测试 LeRobot
python -c "from lerobot.robots.lekiwi import LeKiwi; print('LeRobot OK')"
```

**注意**：`ros-base` 不含示例节点（talker/listener），验证用 `ros2 topic list` 即可。

---

## 4. 跨平台通信验证

> **前提**：PC 和树莓派已完成 ROS2 安装，且在同一 WiFi 局域网。
>
> **示例 IP**（根据你的实际网络修改）：
> - PC: `192.168.3.162`
> - 树莓派: `192.168.3.178`

---

### 4.1 基础检查

**确认双方 ROS_DOMAIN_ID 一致**：

**PC 端**：
```powershell
conda activate ros2
$env:ROS_DOMAIN_ID        # 应输出 42
$env:AMENT_PREFIX_PATH    # 应输出 conda 路径
```

**树莓派端**：
```bash
conda activate ros2
echo $ROS_DOMAIN_ID       # 应输出 42
echo $AMENT_PREFIX_PATH   # 应输出 conda 路径
```

**获取双方 IP 地址**：

**PC 端**：
```powershell
ipconfig
# 找到 WiFi 适配器的 IPv4 地址，如 192.168.3.162
```

**树莓派端**：
```bash
hostname -I
# 应输出 192.168.3.178
```

---

### 4.2 ping 测试（网络层连通性）

**PC 端 ping 树莓派**：
```powershell
ping 192.168.3.178
```

**树莓派端 ping PC**：
```bash
ping 192.168.3.162
```

**预期结果**：双方都能收到回复（`Reply from ...` / `64 bytes from ...`）。

**如果 ping 不通**：
- 检查是否连接同一 WiFi
- Windows 防火墙可能阻止 ICMP，执行：
  ```powershell
  # 以管理员身份运行 PowerShell
  New-NetFirewallRule -DisplayName "Allow Ping" -Direction Inbound -Protocol ICMPv4 -IcmpType 8 -Action Allow
  ```

---

### 4.3 多播测试（DDS 发现机制）

ROS2 默认使用 UDP 多播进行节点发现。

**树莓派端（发送）**：
```bash
ros2 multicast send
```

**PC 端（接收）**：
```powershell
ros2 multicast receive
```

**预期结果**：PC 显示 `Received from 192.168.3.178: hello world`

**实际情况**：家用路由器常阻止设备间多播，此测试**可能失败**，属于正常现象。

---

### 4.4 Topic 互通测试（核心验证）

如果多播测试失败，跳过它，直接用 Topic 测试验证通信。

#### 测试 1：树莓派发布 → PC 接收

**树莓派端（发布）**：
```bash
conda activate ros2
ros2 topic pub /test std_msgs/String "data: 'hello from Pi'"
```

**PC 端（接收）**：
```powershell
conda activate ros2
ros2 topic list
# 应能看到 /test

ros2 topic echo /test
# 应持续输出：
# data: hello from Pi
# ---
```

#### 测试 2：PC 发布 → 树莓派接收

**PC 端（发布）**：
```powershell
ros2 topic pub /pc_test std_msgs/String "data: 'hello from PC'"
```

**树莓派端（接收）**：
```bash
ros2 topic echo /pc_test
# 应持续输出：
# data: hello from PC
# ---
```

**如果 Topic 互相看不到**，使用静态对等节点（见 4.5 节）。

---

### 4.5 备用方案：静态对等节点

如果 DDS 多播被路由器阻止，双方强制指定对端 IP：

**PC 端（加入 activate hook）**：
```powershell
$hookPath = "$env:CONDA_PREFIX\etc\conda\activate.d\ros2_setup.ps1"
$env:ROS_STATIC_PEERS = "192.168.3.178"
# 追加到 hook 文件
"`$env:ROS_STATIC_PEERS = `"192.168.3.178`"" | Add-Content $hookPath
```

**树莓派端（加入 activate hook）**：
```bash
cat >> $CONDA_PREFIX/etc/conda/activate.d/ros2_setup.sh << 'EOF'
export ROS_STATIC_PEERS="192.168.3.162"
EOF
```

**验证**：
```bash
# 双方重新激活环境
conda deactivate
conda activate ros2

# 检查变量
echo $ROS_STATIC_PEERS        # Linux
$env:ROS_STATIC_PEERS         # Windows

# 再次测试 topic
ros2 topic list
ros2 topic echo /test
```

---

## 5. 国内镜像加速（可选）

如果 conda 下载慢，配置国内镜像：

```bash
# 临时使用（单次有效）
conda install -c https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge ros-jazzy-desktop

# 或永久配置（编辑 ~/.condarc）
cat > ~/.condarc << EOF
channels:
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free
  - defaults
show_channel_urls: true
EOF
```

---

## 6. 常见问题 (FAQ)

### Q1: conda 环境里找不到 `ros2` 命令？

```bash
# 确保激活了环境
conda activate ros2

# 如果仍没有，可能需要手动 source  setup 文件
# Linux
source $CONDA_PREFIX/setup.bash
# Windows
# conda 环境的 setup 通常已自动配置
```

### Q2: Windows 上 `rclpy` 导入失败？

```powershell
# 通常是 Python DLL 路径问题
# 确保使用 conda 环境中的 Python
which python  # 应指向 conda env 路径

# 如果 VS Code 中无法导入，在 settings.json 中指定 Python 解释器路径
```

### Q3: 树莓派 conda 安装 ROS2 很慢或报错？

ARM64 上部分包可能没有预编译。解决方案：
```bash
# 方案 A：使用 apt 安装 ROS2（系统级），更稳定
sudo apt install ros-jazzy-ros-base
# 然后 conda 环境只用于 LeRobot 和其他 pip 包

# 方案 B：conda 只装 ros-base（不含 GUI）
conda install ros-jazzy-ros-base -y
```

### Q4: PC 和树莓派安装的包为什么不一样？

| 平台 | 推荐安装 | 原因 |
|------|---------|------|
| PC (Windows 11) | `ros-jazzy-desktop` | 有图形界面，后续要用 RViz2 |
| 树莓派 (headless) | `ros-jazzy-ros-base` | 无显示器，不需要 GUI 工具 |

### Q4: `game_controller_node` 找不到手柄？

```bash
# 枚举可用设备
ros2 run joy joy_enumerate_devices

# 指定设备名
ros2 run joy game_controller_node --ros-args -p device_name:="Xbox Controller"
```

### Q5: `ros2 run` 报错 "Package not found"？

可能是 `AMENT_PREFIX_PATH` 设置错误。

```bash
# 检查路径
echo $AMENT_PREFIX_PATH

# Linux 正确值（无 /Library 后缀）
export AMENT_PREFIX_PATH="$CONDA_PREFIX"

# Windows 正确值（有 /Library 后缀）
$env:AMENT_PREFIX_PATH = "$env:CONDA_PREFIX\Library"

# 刷新 daemon
ros2 daemon stop
ros2 daemon start
```

**Linux vs Windows 差异**：
- Linux: `$CONDA_PREFIX`（可执行文件在 `lib/`）
- Windows: `$CONDA_PREFIX/Library`（可执行文件在 `Library/bin/`）

### Q6: 如何退出 conda 环境？

```bash
conda deactivate
```

---

## 7. 版本迭代记录

| 日期 | 操作 | 内容摘要 |
|------|------|---------|
| 2026-06-05 | 创建 | 初始版本，PC+树莓派 conda 安装指南 |
| 2026-06-05 | 更新 | 新增 2.5 节：配置 ROS2 环境变量自动加载（PowerShell activate hook） |
| 2026-06-05 | 更新 | activate hook 包含 ROS_DOMAIN_ID，删除旧 profile 方法 |
| 2026-06-05 | 更新 | 修正树莓派安装：删除 joy 包、修正 AMENT_PREFIX_PATH 路径、添加 Linux/Windows 路径差异说明 |
