# Phase 1 架构设计：手柄遥控 LeKiwi 底盘

## 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v2.0 |
| 日期 | 2026-06-06 |
| 分支 | `feature/phase1-chassis-teleop` |
| 状态 | ✅ 已完成 |

---

## 1. 目标与范围

### 1.1 目标

使用 ROS2 作为通信与调度框架，在 PC 端通过游戏手柄发送底盘运动指令，经 WiFi 传输到树莓派 5，由树莓派上的 ROS2 节点调用 LeRobot API 驱动 LeKiwi 底盘运动。

### 1.2 范围

- **包含**：手柄读取、速度指令映射、跨网络 Topic 传输、底盘执行
- **不包含**：摄像头（Phase 2）、里程计/SLAM（Phase 4）、机械臂控制（Phase 3）、导航（Phase 5）

---

## 2. 硬件环境

| 组件 | 型号/配置 | 运行环境 | 职责 |
|------|----------|----------|------|
| 上位机 | AMD Ryzen 9 9955HX, RTX 5070Ti Laptop, Windows 11 | PC 端 | 运行手柄节点、遥操作节点、可视化 |
| 树莓派 | Raspberry Pi 5 Model B, 8GB RAM | Ubuntu 24.04 | 运行底盘驱动节点、连接 LeKiwi 硬件 |
| 底盘 | LeKiwi（三轮全向底盘） | 树莓派端 | 接收速度指令，执行运动 |
| 手柄 | Alante Li Wireless Controller | PC 端 | 人机交互输入 |
| 通信 | WiFi（家庭局域网） | — | DDS 中间件自动处理 |

---

## 3. 系统架构

### 3.1 总体架构图

```
PC 端 (Windows 11)
├── joy_node (ROS2 joy 包)
│   └── 发布 /joy (sensor_msgs/Joy)
├── joy_to_cmd_vel (自定义 Python)
│   └── 订阅 /joy，发布 /cmd_vel (geometry_msgs/Twist)
└── tools/image_viewer.py (可选，查看摄像头)

WiFi (ROS2 DDS, ROS_DOMAIN_ID=42)

树莓派端 (Ubuntu 24.04)
└── base_node (自定义 Python)
    ├── 订阅 /cmd_vel
    ├── 调用 LeRobot API 驱动底盘
    └── (Phase 2) 发布 /camera/front/image_raw, /camera/wrist/image_raw
```

### 3.2 架构分层说明

| 层级 | PC 端 | 树莓派端 |
|------|-------|---------|
| **应用层** | `joy_to_cmd_vel`（键位映射、速度转换） | `base_node`（接收指令、安全监控） |
| **通信层** | ROS2 DDS（发布 `/joy`、`/cmd_vel`） | ROS2 DDS（订阅 `/cmd_vel`） |
| **驱动层** | `joy` 驱动（SDL2） | LeRobot `LeKiwi` 类（串口通信） |
| **硬件层** | Alante Li 手柄 | Feetech STS3215 电机 × 3 |

---

## 4. 节点详细设计

### 4.1 joy_node（PC 端）

- **来源**：ROS2 官方 `joy` 包
- **作用**：读取手柄，发布 `/joy`
- **重要**：我们使用 `joy_node`（非 `game_controller_node`），因为 Alante Li 手柄的 D-pad 在 `joy_node` 中映射为 hat（axes），更符合实际使用
- **发布 Topic**：`/joy`
- **消息类型**：`sensor_msgs/Joy`
- **运行方式**：`ros2 run joy joy_node`

#### Joy 消息结构（Alante Li 手柄实际映射）

```yaml
std_msgs/Header header
float32[] axes      # 6 axes + 2 hat axes = 8 total
int32[] buttons     # 16 buttons
```

**Axes 索引**（经过 hat 追加后）：

| 索引 | 原始 axes | 含义 |
|------|----------|------|
| 0-5 | axes[0-5] | 摇杆/扳机（未使用） |
| 6 | hat_x | D-pad 左右（左=1, 右=-1） |
| 7 | hat_y | D-pad 上下（上=1, 下=-1） |

**Buttons 索引**：

| 索引 | 含义 |
|------|------|
| 0 | A |
| 1 | B |
| 3 | X |
| 4 | Y |
| 6 | LB |
| 7 | RB |
| 10 | BACK |
| 11 | START |

> **注意**：SDL2 joy_node 的 hat_x 极性与 pygame 相反：`左=+1, 右=-1`

---

### 4.2 joy_to_cmd_vel（PC 端，自定义）

- **作用**：将 `/joy` 消息按 LeKiwi 键位规则转换为底盘速度指令
- **订阅**：`/joy`
- **发布**：`/cmd_vel`
- **消息类型**：`geometry_msgs/Twist`

#### 核心逻辑

```python
class JoyToCmdVel(Node):
    def joy_callback(self, msg):
        twist = Twist()
        
        if len(msg.axes) >= 8:
            hat_x = msg.axes[6]   # D-pad 左右（SDL2: 左=1, 右=-1）
            hat_y = msg.axes[7]   # D-pad 上下（上=1, 下=-1）
            rb = msg.buttons[7]   # RB 按钮
            
            if rb and hat_x > 0:
                # RB + 左 = 逆时针旋转
                twist.angular.z = self.angular_scale
            elif rb and hat_x < 0:
                # RB + 右 = 顺时针旋转
                twist.angular.z = -self.angular_scale
            else:
                # 平移控制
                if hat_y > 0:
                    twist.linear.x = self.linear_scale    # 前进
                elif hat_y < 0:
                    twist.linear.x = -self.linear_scale   # 后退
                
                if hat_x > 0:
                    twist.linear.y = self.linear_scale    # 左平移
                elif hat_x < 0:
                    twist.linear.y = -self.linear_scale   # 右平移
        
        self.pub.publish(twist)
```

---

### 4.3 base_node（树莓派端，自定义）

- **作用**：接收 `/cmd_vel`，转换为 LeRobot action，驱动底盘
- **订阅**：`/cmd_vel`
- **参数**：
  - `port` (str): 串口路径，默认 `/dev/ttyACM0`
  - `robot_id` (str): 机器人 ID，默认 `lekiwi`
  - `watchdog_timeout_ms` (int): 看门狗超时，默认 500
  - `control_freq` (float): 控制频率，默认 30.0
  - `use_cameras` (bool): 启用摄像头，默认 False

#### 核心逻辑

```python
class LekiwiBaseNode(Node):
    def __init__(self):
        super().__init__('lekiwi_base_node')
        
        # 初始化 LeRobot
        config = LeKiwiConfig(port='/dev/ttyACM0', id='lekiwi')
        self.robot = LeKiwi(config)
        self.robot.connect()
        
        # 订阅 /cmd_vel
        self.cmd_sub = self.create_subscription(
            Twist, '/cmd_vel', self.cmd_vel_callback, 10
        )
        
        # 看门狗
        self.last_cmd_time = self.get_clock().now()
        self.watchdog_timer = self.create_timer(0.25, self.watchdog_callback)
        
        # 控制循环
        self.control_timer = self.create_timer(1/30, self.control_callback)
    
    def cmd_vel_callback(self, msg):
        """收到速度指令，更新当前动作"""
        self.current_action = self._make_zero_action()
        self.current_action["x.vel"] = msg.linear.x
        self.current_action["y.vel"] = msg.linear.y
        self.current_action["theta.vel"] = math.degrees(msg.angular.z)
        self.last_cmd_time = self.get_clock().now()
    
    def control_callback(self):
        """定时发送动作到底盘"""
        self.robot.send_action(self.current_action)
    
    def watchdog_callback(self):
        """超时未收到指令则停止"""
        if (self.get_clock().now() - self.last_cmd_time) > timeout:
            self.robot.send_action(self._make_zero_action())
```

#### 机械臂默认姿态

当停止运动时，机械臂保持以下姿态（非零）：

```python
ARM_DEFAULTS = {
    "arm_shoulder_pan.pos": 0.0,
    "arm_shoulder_lift.pos": -100.0,
    "arm_elbow_flex.pos": 90.0,
    "arm_wrist_flex.pos": 70.0,
    "arm_wrist_roll.pos": 0.0,
    "arm_gripper.pos": 0.0,
}
```

---

## 5. 消息定义与 Topic

### 5.1 Topic 列表

| Topic | 类型 | 发布者 | 订阅者 | 说明 |
|-------|------|--------|--------|------|
| `/joy` | `sensor_msgs/Joy` | `joy_node` | `joy_to_cmd_vel` | 手柄原始输入 |
| `/cmd_vel` | `geometry_msgs/Twist` | `joy_to_cmd_vel` | `base_node` | 底盘速度指令 |
| `/camera/front/image_raw` | `sensor_msgs/Image` | `base_node` | `image_viewer` | front 摄像头 (Phase 2) |
| `/camera/wrist/image_raw` | `sensor_msgs/Image` | `base_node` | `image_viewer` | wrist 摄像头 (Phase 2) |

### 5.2 geometry_msgs/Twist 字段说明

```yaml
geometry_msgs/Vector3 linear
  float64 x   # 前进/后退速度 (m/s)
  float64 y   # 左/右平移速度 (m/s)，全向底盘才有
  float64 z   # 固定为 0

geometry_msgs/Vector3 angular
  float64 x   # 固定为 0
  float64 y   # 固定为 0
  float64 z   # 偏航角速度 (rad/s)
```

> **单位约定**：ROS2 标准中角速度使用 **rad/s**，但 LeRobot 内部使用 **deg/s**。在 `base_node` 中需要进行单位转换。

---

## 6. 手柄键位映射

### 6.1 Phase 1 键位表

| 按键 | 功能 | Joy 消息 | 输出 |
|------|------|----------|------|
| D-pad 上 | 前进 | `axes[7] = 1` | `linear.x = +speed` |
| D-pad 下 | 后退 | `axes[7] = -1` | `linear.x = -speed` |
| D-pad 左 | 左平移 | `axes[6] = 1` | `linear.y = +speed` |
| D-pad 右 | 右平移 | `axes[6] = -1` | `linear.y = -speed` |
| RB + D-pad 左 | 逆时针旋转 | `buttons[7] + axes[6]=1` | `angular.z = +scale` |
| RB + D-pad 右 | 顺时针旋转 | `buttons[7] + axes[6]=-1` | `angular.z = -scale` |

### 6.2 重要说明

- **SDL2 hat_x 极性**：`joy_node` 中 `左=+1, 右=-1`（与 pygame 相反）
- **D-pad 是 axes**：在 `joy_node` 中 D-pad 映射为 hat，追加到 axes 末尾（axes[6], axes[7]）
- **不需要 SDL_GAMECONTROLLERCONFIG**：`joy_node` 原生支持 Alante Li 手柄

---

## 7. 工作空间目录结构

```
lerobot-ros2/
├── README.md
├── .gitignore
├── requirements.txt
├── docs/
│   ├── architecture/
│   │   ├── phase1_chassis_teleop.md      # 本文档
│   │   ├── installation-guide.md         # 环境安装
│   │   └── pre-coding-research.md        # 预研文档
│   └── runbooks/
│       ├── phase2-camera-streaming.md    # Phase 2 摄像头
│       └── topic-debugging.md            # 调试技巧
├── tools/                                 # 调试工具
│   ├── topic_monitor.py                  # Topic 变化监视器
│   ├── test_gamepad.py                   # 手柄硬件测试
│   └── image_viewer.py                   # ROS2 图像查看器
└── src/                                   # ROS2 工作空间
    ├── lekiwi_teleop/                     # PC 端遥操作包
    │   ├── lekiwi_teleop/
    │   │   ├── __init__.py
    │   │   └── joy_to_cmd_vel.py          # joy → cmd_vel 转换
    │   ├── package.xml
    │   ├── setup.py
    │   └── resource/lekiwi_teleop
    │
    ├── lekiwi_base/                        # 树莓派端底盘驱动包
    │   ├── lekiwi_base/
    │   │   ├── __init__.py
    │   │   └── base_node.py               # 底盘控制 + 摄像头
    │   ├── package.xml
    │   ├── setup.py
    │   └── resource/lekiwi_base
    │
    └── lekiwi_bringup/                     # 统一启动与配置
        ├── launch/
        │   ├── pc_teleop.launch.py         # PC 端启动
        │   └── pi_base.launch.py           # 树莓派端启动
        ├── package.xml
        └── setup.py
```

---

## 8. 与后续阶段的衔接

### Phase 2：摄像头（已实现）

在 `base_node` 中启用 `use_cameras:=true`：
- 读取 front (/dev/video2) 和 wrist (/dev/video0) 摄像头
- 发布到 `/camera/front/image_raw` 和 `/camera/wrist/image_raw`
- 摄像头读取在独立后台线程，不阻塞底盘控制

### Phase 3：机械臂遥操作

- 在 PC 端添加主臂读取节点
- 在树莓派端扩展 `base_node` 控制从臂
- 记录遥操作数据用于模仿学习

### Phase 4：里程计 + SLAM

- 读取电机编码器位置计算里程计
- 发布 `/odom` 和 `/tf`
- 集成 Nav2 导航框架

---

## 9. 依赖与安装

详见 [installation-guide.md](installation-guide.md)

快速命令：
```bash
# PC 端
conda activate ros2
pip install -e src/lekiwi_teleop/

# 树莓派端
conda activate ros2
pip install -e src/lekiwi_base/
```

---

## 10. 调试工具

| 工具 | 用途 | 命令 |
|------|------|------|
| `topic_monitor.py` | 监视 Topic 变化（不刷屏） | `python tools/topic_monitor.py /joy` |
| `test_gamepad.py` | 测试手柄硬件 | `python tools/test_gamepad.py` |
| `image_viewer.py` | 查看摄像头图像 | `python tools/image_viewer.py --ros-args -p topic:=/camera/front/image_raw` |

---

## 版本迭代记录

| 日期 | 版本 | 内容摘要 |
|------|------|---------|
| 2026-06-05 | v1.0 | 初始版本，基于 game_controller_node |
| 2026-06-05 | v1.1 | 修正 D-pad 映射、Windows 支持说明 |
| 2026-06-06 | v2.0 | **重大更新**：改用 joy_node、添加 hat 映射、添加 joy_to_cmd_vel、更新文件结构、添加调试工具 |
