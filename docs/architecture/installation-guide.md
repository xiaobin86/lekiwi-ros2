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

### 2.5 安装开发依赖

```powershell
# 在 ros2 环境中安装 pip 包
pip install numpy pillow pyserial

# 安装 colcon（如果 conda 没有）
pip install colcon-common-extensions
```

### 2.6 验证安装

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

### 2.7 Windows 防火墙配置

首次运行 ROS2 节点时，Windows 会弹出防火墙提示：

1. 勾选 **专用网络** 和 **公用网络**
2. 点击 **允许访问**

如果之前拒绝了，手动添加规则：

```powershell
# 以管理员身份运行 PowerShell
New-NetFirewallRule -DisplayName "ROS2 Python" -Direction Inbound -Program "$(conda activate ros2 && python -c "import sys; print(sys.executable)")" -Action Allow
```

### 2.8 环境变量配置（可选）

将以下内容添加到 PowerShell profile（`$PROFILE`）：

```powershell
# 自动激活 ros2 环境
function ros2-env {
    conda activate ros2
    $env:ROS_DOMAIN_ID = 42
    $env:ROS_AUTOMATIC_DISCOVERY_RANGE = "SUBNET"
}

# 使用: 打开新终端后执行 ros2-env
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
# 安装桌面版
conda install ros-jazzy-desktop -y

# 安装工具
conda install colcon-common-extensions -y
```

> **注意**：ARM64 上某些包可能没有预编译二进制，需要编译。如果遇到 `PackagesNotFoundError`，尝试：
> ```bash
> conda install ros-jazzy-ros-base -y  # 先装基础版
> # 再按需安装其他包
> ```

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

### 3.7 验证安装

```bash
# 激活环境
conda activate ros2

# 检查 ROS2
ros2 --version

# 测试 talker/listener（开两个终端）
# 终端 1
ros2 run demo_nodes_cpp talker
# 终端 2
ros2 run demo_nodes_py listener

# 测试 LeRobot
python -c "from lerobot.robots.lekiwi import LeKiwi; print('LeRobot OK')"
```

### 3.8 环境变量配置

添加到 `~/.bashrc`：

```bash
# ROS2 快速激活别名
alias ros2-env='conda activate ros2 && export ROS_DOMAIN_ID=42 && export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET'

# 可选：打开终端自动激活（不推荐，会减慢终端启动）
# conda activate ros2 2>/dev/null
# export ROS_DOMAIN_ID=42
```

---

## 4. 跨平台通信验证

### 4.1 统一环境变量

**PC (Windows PowerShell)**：
```powershell
conda activate ros2
$env:ROS_DOMAIN_ID = 42
$env:ROS_AUTOMATIC_DISCOVERY_RANGE = "SUBNET"
```

**树莓派 (Bash)**：
```bash
conda activate ros2
export ROS_DOMAIN_ID=42
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
```

### 4.2 多播连通性测试

```bash
# 树莓派（发送）
ros2 multicast send

# PC（接收）
ros2 multicast receive
# 应该收到 "Received from xxx.xxx.xxx.xxx: hello world"
```

如果收不到：
- 检查防火墙（Windows 必须允许）
- 检查是否同一 WiFi
- 尝试静态对等节点：
  ```bash
  export ROS_STATIC_PEERS="192.168.x.x"  # 对端 IP
  ```

### 4.3 Topic 互通测试

```bash
# PC 端发布测试消息
ros2 topic pub /test std_msgs/String "data: hello from PC"

# 树莓派端接收
ros2 topic echo /test
# 应该看到消息
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

ARM64 上部分包可能没有预编译。替代方案：
```bash
# 方案 A：使用 apt 安装 ROS2（系统级），conda 只装 Python 依赖
sudo apt install ros-jazzy-desktop ros-jazzy-joy
# 然后 conda 环境只用于 LeRobot 和其他 pip 包

# 方案 B：使用 ros-base 减少依赖
conda install ros-jazzy-ros-base -y
```

### Q4: `game_controller_node` 找不到手柄？

```bash
# 枚举可用设备
ros2 run joy joy_enumerate_devices

# 指定设备名
ros2 run joy game_controller_node --ros-args -p device_name:="Xbox Controller"
```

### Q5: 如何退出 conda 环境？

```bash
conda deactivate
```

---

## 7. 版本迭代记录

| 日期 | 操作 | 内容摘要 |
|------|------|---------|
| 2026-06-05 | 创建 | 初始版本，PC+树莓派 conda 安装指南 |
