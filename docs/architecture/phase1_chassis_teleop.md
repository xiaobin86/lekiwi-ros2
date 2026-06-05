# Phase 1 架构设计：手柄遥控 LeKiwi 底盘

## 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v1.0 |
| 日期 | 2026-06-05 |
| 分支 | `feature/phase1-chassis-teleop` |
| 目标 | 基于 ROS2 实现 PC 手柄 → WiFi → 树莓派 → LeKiwi 底盘遥控 |

---

## 1. 目标与范围

### 1.1 目标

使用 ROS2 作为通信与调度框架，在 PC 端通过 Xbox 手柄发送底盘运动指令，经 WiFi 传输到树莓派 5，由树莓派上的 ROS2 节点调用 LeRobot API 驱动 LeKiwi 底盘运动。

### 1.2 范围

- **包含**：手柄读取、速度指令映射、跨网络 Topic 传输、底盘执行
- **不包含**：摄像头（Phase 2）、里程计/SLAM（Phase 3）、机械臂控制（Phase 4）、导航（Phase 4）
- **学习方式**：Phase 1 重点理解 ROS2 的 Node、Topic、Message、Launch 核心概念

---

## 2. 硬件环境

| 组件 | 型号/配置 | 运行环境 | 职责 |
|------|----------|----------|------|
| 上位机 | AMD Ryzen 9 9955HX, RTX 5070Ti Laptop, Windows 11 | PC 端 | 运行手柄节点、遥操作节点、可视化 |
| 树莓派 | Raspberry Pi 5 Model B, 8GB RAM | Ubuntu 24.04 / Raspberry Pi OS | 运行底盘驱动节点、连接 LeKiwi 硬件 |
| 底盘 | LeKiwi（三轮全向底盘） | 树莓派端 | 接收速度指令，执行运动 |
| 从臂 | SO101 Follower Arm (ID: R12552802) | 树莓派端 | **Phase 1 不启用** |
| 主臂 | SO101 Leader Arm (ID: L07252802) | PC 端 | **Phase 1 不启用** |
| 手柄 | Xbox Controller | PC 端 | 人机交互输入 |
| 通信 | WiFi（家庭局域网） | — | DDS 中间件自动处理 |

### 2.1 LeKiwi 底盘关键参数

- **驱动方式**：Kiwi Drive（三轮全向，120° 均匀分布）
- **电机型号**：Feetech STS3215 × 3（ID: 7/8/9）
- **串口**：`/dev/ttyACM0`
- **轮子半径**：0.05 m
- **底盘半径**：0.125 m（旋转中心到轮子距离）
- **控制模式**：速度模式（`Operating_Mode = VELOCITY`）

---

## 3. 系统架构

### 3.1 总体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PC 端 (Windows 11)                                 │
│                                                                              │
│   ┌──────────────┐         ┌─────────────────────────┐                      │
│   │ Xbox 手柄    │  USB    │   joy_node              │                      │
│   │ (物理设备)    │────────▶│   (joy package)         │                      │
│   └──────────────┘         │   读取手柄原始状态        │                      │
│                            │   发布 /joy              │                      │
│                            └───────────┬─────────────┘                      │
│                                        │ sensor_msgs/Joy                   │
│                                        ▼                                    │
│                            ┌─────────────────────────┐                      │
│                            │   lekiwi_teleop_node    │                      │
│                            │   (自定义 Python)        │                      │
│                            │   - D-pad → 平移速度     │                      │
│                            │   - RB+方向 → 旋转速度   │                      │
│                            │   - LB → 切换速度档      │                      │
│                            │   - START → 退出        │                      │
│                            └───────────┬─────────────┘                      │
│                                        │ geometry_msgs/Twist               │
│                                        ▼                                    │
│                            ┌─────────────────────────┐                      │
│                            │   /cmd_vel (Topic)      │                      │
│                            └───────────┬─────────────┘                      │
│                                        │                                    │
└────────────────────────────────────────┼────────────────────────────────────┘
                                         │  DDS over WiFi
                                         │  (ROS_DOMAIN_ID 一致)
┌────────────────────────────────────────┼────────────────────────────────────┐
│                     树莓派端 (Ubuntu)    │                                    │
│                                        ▼                                    │
│                            ┌─────────────────────────┐                      │
│                            │   lekiwi_base_node      │                      │
│                            │   (自定义 Python)        │                      │
│                            │   订阅 /cmd_vel          │                      │
│                            │   调用 LeRobot API       │                      │
│                            │   看门狗安全保护         │                      │
│                            └───────────┬─────────────┘                      │
│                                        │                                    │
│                            ┌───────────▼─────────────┐                      │
│                            │   LeRobot LeKiwi        │                      │
│                            │   - FeetechMotorsBus    │                      │
│                            │   - /dev/ttyACM0        │                      │
│                            │   - 速度模式控制        │                      │
│                            └───────────┬─────────────┘                      │
│                                        │ 串口指令                            │
│                            ┌───────────▼─────────────┐                      │
│                            │   LeKiwi 底盘           │                      │
│                            │   (3×全向轮)            │                      │
│                            └─────────────────────────┘                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 架构分层说明

| 层级 | PC 端 | 树莓派端 |
|------|-------|---------|
| **应用层** | `lekiwi_teleop_node`（键位映射、速度转换） | `lekiwi_base_node`（接收指令、安全监控） |
| **通信层** | ROS2 DDS（发布 `/joy`、`/cmd_vel`） | ROS2 DDS（订阅 `/cmd_vel`） |
| **驱动层** | `joy` 驱动（操作系统手柄驱动） | LeRobot `LeKiwi` 类（串口通信） |
| **硬件层** | Xbox 手柄 | Feetech STS3215 电机 × 3 |

---

## 4. 节点详细设计

### 4.1 joy_node（PC 端）

- **来源**：ROS2 官方 `joy` 包
- **作用**：读取操作系统识别到的手柄设备，将原始输入封装为 ROS2 标准消息
- **发布 Topic**：`/joy`
- **消息类型**：`sensor_msgs/Joy`
- **运行方式**：`ros2 run joy joy_node`

#### Joy 消息结构

```yaml
std_msgs/Header header
float32[] axes      # 摇杆/扳机模拟值 [-1.0, 1.0]
int32[] buttons     # 按钮状态 [0, 1]
```

对于 Xbox 手柄（Linux/SDL2 映射）：

| 索引 | axes | 含义 |
|------|------|------|
| 0 | axes[0] | 左摇杆 X |
| 1 | axes[1] | 左摇杆 Y |
| 2 | axes[2] | 左扳机 LT |
| 3 | axes[3] | 右摇杆 X |
| 4 | axes[4] | 右摇杆 Y |
| 5 | axes[5] | 右扳机 RT |
| 6 | axes[6] | D-pad X（方向键左右） |
| 7 | axes[7] | D-pad Y（方向键上下） |

| 索引 | buttons | 含义 |
|------|---------|------|
| 0 | buttons[0] | A |
| 1 | buttons[1] | B |
| 2 | buttons[2] | X |
| 3 | buttons[3] | Y |
| 4 | buttons[4] | LB |
| 5 | buttons[5] | RB |
| 6 | buttons[6] | BACK |
| 7 | buttons[7] | START |
| 8 | buttons[8] | XBox 键 |
| 9 | buttons[9] | 左摇杆按下 |
| 10 | buttons[10] | 右摇杆按下 |

> **注意**：Windows 下的 `joy` 包映射可能与 Linux 不同，实际开发时需用 `ros2 topic echo /joy` 确认。

---

### 4.2 lekiwi_teleop_node（PC 端，自定义）

- **作用**：将 `/joy` 消息按 LeKiwi 键位规则转换为底盘速度指令
- **订阅**：`/joy`
- **发布**：`/cmd_vel`
- **消息类型**：`geometry_msgs/Twist`

#### 核心逻辑

```python
class LekiwiTeleopNode(Node):
    def __init__(self):
        super().__init__('lekiwi_teleop_node')
        
        # 声明参数
        self.declare_parameter('max_linear_speed', 0.5)   # m/s
        self.declare_parameter('max_angular_speed', 90.0) # deg/s
        self.declare_parameter('speed_levels', [0.1, 0.3, 0.5])
        
        # 订阅 /joy
        self.joy_sub = self.create_subscription(
            Joy, '/joy', self.joy_callback, 10
        )
        
        # 发布 /cmd_vel
        self.cmd_pub = self.create_publisher(
            Twist, '/cmd_vel', 10
        )
        
        self.speed_index = 1  # 默认中速
        self.prev_lb = False   # LB 边沿检测
    
    def joy_callback(self, msg: Joy):
        # LB 切换速度档（边沿检测）
        lb_current = msg.buttons[4] == 1
        if lb_current and not self.prev_lb:
            self.speed_index = (self.speed_index + 1) % 3
        self.prev_lb = lb_current
        
        speed = self.speed_levels[self.speed_index]
        
        # D-pad 读取（axes[6] 左右, axes[7] 上下）
        # 注意：axes 值通常为 -1, 0, 1，但有些驱动是 0/1 按钮式
        hat_x = msg.axes[6] if len(msg.axes) > 6 else 0.0
        hat_y = msg.axes[7] if len(msg.axes) > 7 else 0.0
        rb_pressed = msg.buttons[5] == 1
        
        twist = Twist()
        
        if rb_pressed:
            # RB + 左右 = 原地旋转
            if hat_x < 0:
                twist.angular.z = math.radians(self.max_angular_speed)
            elif hat_x > 0:
                twist.angular.z = -math.radians(self.max_angular_speed)
        else:
            # 平移控制
            if hat_y > 0:
                twist.linear.x = speed          # 前进
            elif hat_y < 0:
                twist.linear.x = -speed         # 后退
            
            if hat_x < 0:
                twist.linear.y = speed          # 左平移
            elif hat_x > 0:
                twist.linear.y = -speed         # 右平移
        
        self.cmd_pub.publish(twist)
```

---

### 4.3 lekiwi_base_node（树莓派端，自定义）

- **作用**：接收 `/cmd_vel`，转换为 LeRobot action，驱动底盘，同时提供安全保护
- **订阅**：`/cmd_vel`
- **依赖**：LeRobot `LeKiwi` 类

#### 核心逻辑

```python
class LekiwiBaseNode(Node):
    def __init__(self):
        super().__init__('lekiwi_base_node')
        
        # 声明参数
        self.declare_parameter('port', '/dev/ttyACM0')
        self.declare_parameter('watchdog_timeout_ms', 500)
        
        # 初始化 LeRobot
        from lerobot.robots.lekiwi import LeKiwi
        from lerobot.robots.lekiwi.config_lekiwi import LeKiwiConfig
        
        config = LeKiwiConfig(port=self.get_parameter('port').value)
        self.robot = LeKiwi(config)
        self.robot.connect()
        
        # 订阅 /cmd_vel
        self.cmd_sub = self.create_subscription(
            Twist, '/cmd_vel', self.cmd_vel_callback, 10
        )
        
        # 看门狗定时器
        self.last_cmd_time = self.get_clock().now()
        self.watchdog_timer = self.create_timer(0.1, self.watchdog_callback)
    
    def cmd_vel_callback(self, msg: Twist):
        """收到速度指令，转换为 LeRobot action 并发送"""
        action = {
            "x.vel": msg.linear.x,           # m/s
            "y.vel": msg.linear.y,           # m/s
            "theta.vel": math.degrees(msg.angular.z),  # deg/s
            # Phase 1 不控制机械臂，发送默认值
            "arm_shoulder_pan.pos": 0.0,
            "arm_shoulder_lift.pos": 0.0,
            "arm_elbow_flex.pos": 0.0,
            "arm_wrist_flex.pos": 0.0,
            "arm_wrist_roll.pos": 0.0,
            "arm_gripper.pos": 0.0,
        }
        
        self.robot.send_action(action)
        self.last_cmd_time = self.get_clock().now()
    
    def watchdog_callback(self):
        """看门狗：超时未收到指令则停止底盘"""
        now = self.get_clock().now()
        timeout = rclpy.duration.Duration(
            seconds=self.get_parameter('watchdog_timeout_ms').value / 1000.0
        )
        
        if now - self.last_cmd_time > timeout:
            self.get_logger().warning("Watchdog timeout! Stopping base.")
            self.robot.stop_base()
```

#### 看门狗机制说明

LeRobot 的 `lekiwi_host.py` 自带 500ms 看门狗（`watchdog_timeout_ms`），我们的 ROS2 节点也独立实现一层看门狗，双重保护确保网络抖动或程序崩溃时底盘自动停车。

---

## 5. 消息定义与 Topic

### 5.1 Topic 列表

| Topic | 类型 | 发布者 | 订阅者 | 说明 |
|-------|------|--------|--------|------|
| `/joy` | `sensor_msgs/Joy` | `joy_node` | `lekiwi_teleop_node` | 手柄原始输入 |
| `/cmd_vel` | `geometry_msgs/Twist` | `lekiwi_teleop_node` | `lekiwi_base_node` | 底盘速度指令 |

### 5.2 geometry_msgs/Twist 字段说明

```yaml
geometry_msgs/Vector3 linear
  float64 x   # 前进/后退速度 (m/s)
  float64 y   # 左/右平移速度 (m/s)，全向底盘才有
  float64 z   # 垂直方向，底盘固定为 0

geometry_msgs/Vector3 angular
  float64 x   # 横滚角速度，固定为 0
  float64 y   # 俯仰角速度，固定为 0
  float64 z   # 偏航角速度 (rad/s)，正=逆时针
```

> **单位约定**：ROS2 标准中角速度使用 **rad/s**，但 LeRobot 内部使用 **deg/s**。在 `lekiwi_base_node` 中需要进行单位转换。

---

## 6. 手柄键位映射

### 6.1 Phase 1 键位表

| 按键 | 功能 | 输出 |
|------|------|------|
| D-pad 上 | 前进 | `linear.x = +speed` |
| D-pad 下 | 后退 | `linear.x = -speed` |
| D-pad 左 | 左平移 | `linear.y = +speed` |
| D-pad 右 | 右平移 | `linear.y = -speed` |
| RB + D-pad 左 | 逆时针旋转 | `angular.z = +max_angular` |
| RB + D-pad 右 | 顺时针旋转 | `angular.z = -max_angular` |
| LB（按下瞬间） | 切换速度档 | Low → Medium → High → Low |
| START | 退出程序 | 发送零速度后节点退出 |

### 6.2 速度档位

| 档位 | linear.x/y (m/s) | angular.z (deg/s) | 适用场景 |
|------|------------------|-------------------|---------|
| Slow (低速) | 0.1 | 30 | 精细调整、靠近目标 |
| Medium (中速) | 0.3 | 60 | 常规移动 |
| Fast (高速) | 0.5 | 90 | 长距离移动 |

### 6.3 与之前 ZMQ 方案的对比

| 特性 | ZMQ 方案（旧） | ROS2 方案（新） |
|------|---------------|----------------|
| 通信协议 | ZMQ PUSH/PULL | ROS2 DDS |
| 消息格式 | JSON dict | 标准 ROS2 Message |
| PC 端角色 | 直接发 action dict | 只发标准化速度指令 |
| Pi 端角色 | 透明转发 | 本地硬件抽象+安全监控 |
| 可扩展性 | 低（硬编码） | 高（任何节点可订阅/发布） |

---

## 7. 工作空间目录结构

```
lerobot-ros2/
├── README.md
├── .gitignore
├── docs/
│   └── architecture/
│       └── phase1_chassis_teleop.md      # 本文档
│
├── src/                                    # ROS2 工作空间 src 目录
│   ├── lekiwi_teleop/                      # PC 端遥操作包
│   │   ├── lekiwi_teleop/
│   │   │   ├── __init__.py
│   │   │   └── teleop_node.py              # 手柄→速度映射节点
│   │   ├── package.xml
│   │   ├── setup.py
│   │   └── resource/lekiwi_teleop
│   │
│   ├── lekiwi_base/                        # 树莓派端底盘驱动包
│   │   ├── lekiwi_base/
│   │   │   ├── __init__.py
│   │   │   └── base_node.py                # 速度指令→底盘节点
│   │   ├── package.xml
│   │   ├── setup.py
│   │   └── resource/lekiwi_base
│   │
│   └── lekiwi_bringup/                     # 统一启动与配置
│       ├── launch/
│       │   ├── pc_teleop.launch.py         # PC 端启动
│       │   └── pi_base.launch.py           # 树莓派端启动
│       ├── config/
│       │   └── teleop_config.yaml          # 速度档、按键映射参数
│       ├── package.xml
│       └── setup.py
│
└── requirements/                           # 非 ROS 依赖说明
    └── requirements.txt
```

---

## 8. ROS2 核心 API 说明

### 8.1 rclpy 常用 API

```python
import rclpy
from rclpy.node import Node

# 初始化 ROS2
rclpy.init()

# 创建节点
node = Node('node_name')

# 声明参数（运行时可通过 launch/命令行修改）
node.declare_parameter('param_name', default_value)
value = node.get_parameter('param_name').value

# 创建发布者
pub = node.create_publisher(MessageType, '/topic_name', qos_profile=10)

# 创建订阅者
def callback(msg):
    pass
sub = node.create_subscription(MessageType, '/topic_name', callback, 10)

# 创建定时器
timer = node.create_timer(period_sec=0.1, callback=timer_callback)

# 获取当前时间
now = node.get_clock().now()

# 打日志
node.get_logger().info("message")
node.get_logger().warning("message")
node.get_logger().error("message")

# 旋转节点（阻塞，处理回调）
rclpy.spin(node)

# 清理
node.destroy_node()
rclpy.shutdown()
```

### 8.2 QoS（服务质量）

ROS2 使用 QoS 控制消息传输策略：

| 策略 | 说明 | 场景 |
|------|------|------|
| **Reliability** | Reliable（可靠） vs Best Effort（尽力） | `/cmd_vel` 用 Best Effort 降低延迟 |
| **Durability** | Volatile（易失） vs Transient Local（持久） | 配置话题可用 Transient Local |
| **History** | Keep Last（保留 N 个） vs Keep All | 实时控制通常 Keep Last(1) |

对于底盘控制，推荐 `/cmd_vel` 使用 **Best Effort + Keep Last(1)**，确保总是处理最新指令而非排队旧指令。

### 8.3 ROS_DOMAIN_ID

ROS2 默认使用 DDS 发现同一网络内所有节点。为避免与其他 ROS2 设备冲突：

```bash
# PC 端和树莓派端必须设置相同的 ID
export ROS_DOMAIN_ID=42

# Windows PowerShell
$env:ROS_DOMAIN_ID=42
```

---

## 9. 与后续阶段的衔接

### 9.1 Phase 2：摄像头与可视化

在 `lekiwi_base_node` 中扩展：

```python
# 读取摄像头并发布
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

self.image_pub = self.create_publisher(Image, '/camera/front', 10)
self.bridge = CvBridge()

# 在循环中
frame = self.robot.cameras['front'].read()
msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
self.image_pub.publish(msg)
```

新增 Topic：
- `/camera/front` (`sensor_msgs/Image`)
- `/camera/wrist` (`sensor_msgs/Image`)
- `/joint_states` (`sensor_msgs/JointState`) — 机械臂关节状态

### 9.2 Phase 3：里程计（Odometry）

#### 方案 A：速度积分（快速实现，有漂移）

在 `lekiwi_base_node` 中：

```python
from nav_msgs.msg import Odometry
from tf2_ros import TransformBroadcaster

self.odom_pub = self.create_publisher(Odometry, '/odom', 10)
self.tf_broadcaster = TransformBroadcaster(self)

# 定时积分
def odom_timer_callback(self):
    obs = self.robot.get_observation()
    vx, vy = obs['x.vel'], obs['y.vel']
    vtheta = math.radians(obs['theta.vel'])
    
    # 积分（简化欧拉法）
    dt = 0.05
    self.x += (vx * math.cos(self.yaw) - vy * math.sin(self.yaw)) * dt
    self.y += (vx * math.sin(self.yaw) + vy * math.cos(self.yaw)) * dt
    self.yaw += vtheta * dt
    
    # 发布 Odometry 消息 + TF
```

#### 方案 B：编码器位置（精度更高）

直接调用 Feetech 电机寄存器读取轮子累计角度：

```python
# LeRobot 底层支持，但 LeKiwi 类未封装
wheel_positions = self.robot.bus.sync_read("Present_Position", self.robot.base_motors)
```

然后根据角度差反解车身位移，精度远高于速度积分。

### 9.3 Phase 4：Nav2 导航

Nav2 需要的标准接口：

| 输入 | 来源 |
|------|------|
| `/cmd_vel` | Nav2 路径规划器输出 |
| `/odom` | Phase 3 里程计节点 |
| `/scan` 或 `/camera/depth` | 需外接激光雷达或深度相机 |
| `/tf` (`odom → base_link`) | 里程计节点发布 |
| `/map` | SLAM 建图节点 |

### 9.4 为什么 Phase 1 不直接用 ros2_control？

| 对比 | 当前方案 (LeRobot API) | ros2_control |
|------|----------------------|-------------|
| Phase 1 开发量 | 低 | 高 |
| 需要 URDF | 否 | 是 |
| 需要硬件接口插件 | 否 | 是 |
| 学习曲线 | 平缓 | 陡峭 |
| Nav2 兼容性 | 需要后续桥接 | 原生支持 |
| **策略** | **先跑通，再渐进桥接** | 后续替换 |

---

## 10. 依赖与安装

### 10.1 PC 端（Windows）

- ROS2 Jazzy Jalisco（Windows 支持）或 ROS2 Humble（WSL2）
- Python 3.12+
- `joy` 包：`ros2 run joy joy_node` 可用
- 手柄驱动：Xbox 手柄 Windows 原生支持

### 10.2 树莓派端（Ubuntu/Raspberry Pi OS）

- ROS2 Jazzy Jalisco（ARM64 版本）
- Python 3.12+
- LeRobot 库（`pip install -e .` 从源码安装）
- 串口权限：`sudo usermod -aG dialout $USER`

### 10.3 双方共同依赖

```xml
<!-- package.xml 中声明 -->
<depend>rclpy</depend>
<depend>std_msgs</depend>
<depend>geometry_msgs</depend>
<depend>sensor_msgs</depend>
<depend>joy</depend>
```

---

## 11. 附录：LeRobot API 实情（基于源码）

以下内容来自对 `D:\work\lerobot-workspace\lerobot\src\lerobot\robots\lekiwi\lekiwi.py` 的实际源码分析。

### 11.1 LeKiwi 类提供的接口

| 方法 | 功能 | 返回值 |
|------|------|--------|
| `connect()` | 连接串口、初始化电机 | None |
| `disconnect()` | 停止底盘、断开连接 | None |
| `send_action(action)` | 发送动作指令 | 实际发送的 action dict |
| `get_observation()` | 读取当前状态 | observation dict |
| `stop_base()` | 强制停止三个轮子 | None |

### 11.2 get_observation() 实际返回内容

```python
{
    # 机械臂关节位置（Phase 1 忽略）
    "arm_shoulder_pan.pos":  float,
    "arm_shoulder_lift.pos": float,
    "arm_elbow_flex.pos":    float,
    "arm_wrist_flex.pos":    float,
    "arm_wrist_roll.pos":    float,
    "arm_gripper.pos":       float,
    
    # 底盘速度（车身坐标系，瞬时反馈）
    "x.vel":       float,   # m/s
    "y.vel":       float,   # m/s
    "theta.vel":   float,   # deg/s
    
    # 摄像头图像（如果有配置）
    "front": np.ndarray,    # (H, W, 3) uint8
    "wrist": np.ndarray,    # (H, W, 3) uint8
}
```

### 11.3 速度反馈的来源

```python
# lekiwi.py:344-351
base_wheel_vel = self.bus.sync_read("Present_Velocity", self.base_motors)
base_vel = self._wheel_raw_to_body(
    base_wheel_vel["base_left_wheel"],
    base_wheel_vel["base_back_wheel"],
    base_wheel_vel["base_right_wheel"],
)
```

流程：
1. 读取三个轮子的 `Present_Velocity` 寄存器（电机原始值）
2. 通过 `_wheel_raw_to_body()` 逆运动学转换为车身坐标系速度
3. 返回 `x.vel`, `y.vel`, `theta.vel`

### 11.4 电机可用寄存器

来自 `D:\work\lerobot-workspace\lerobot\src\lerobot\motors\feetech\tables.py`：

| 寄存器名 | 地址 | 大小 | 读写 | 用途 |
|---------|------|------|------|------|
| `Goal_Position` | 42 | 2B | RW | 目标位置 |
| `Goal_Velocity` | 46 | 2B | RW | 目标速度 |
| `Present_Position` | 56 | 2B | RO | 当前位置（编码器值） |
| `Present_Velocity` | 58 | 2B | RO | 当前速度 |
| `Present_Load` | 60 | 2B | RO | 负载 |
| `Present_Current` | 69 | 2B | RO | 电流 |

### 11.5 关键结论

1. **没有现成 odometry API**：LeRobot 不提供位姿积分，只返回瞬时速度。
2. **可以读编码器位置**：通过 `bus.sync_read("Present_Position", base_motors)` 可以获取轮子累计角度，自己计算里程计。
3. **运动学已封装**：`_body_to_wheel_raw()` 和 `_wheel_raw_to_body()` 已完成全向底盘的正逆运动学，但它们是私有方法。Phase 1 只需要 `send_action()`（正向），不需要直接调用。
4. **底盘电机 ID**：`base_left_wheel=7`, `base_back_wheel=8`, `base_right_wheel=9`。

---

## 12. 风险与注意事项

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Windows 手柄驱动映射与 Linux 不同 | joy 消息索引错位 | 实际测试时先用 `ros2 topic echo /joy` 确认 |
| WiFi 延迟/丢包 | 底盘卡顿或失控 | 看门狗超时自动停车 |
| DDS 网络冲突 | 与其他 ROS2 设备干扰 | 使用唯一 `ROS_DOMAIN_ID` |
| LeRobot 速度单位 | `send_action` 用 deg/s，`Twist` 用 rad/s | `base_node` 中严格转换 |
| 树莓派 CPU 负载 | DDS + LeRobot 可能占用较高 | 监控 `top`，必要时降低 publish 频率 |

---

## 版本迭代记录

| 日期 | 操作 | 内容摘要 |
|------|------|---------|
| 2026-06-05 | 创建 | 初始版本，基于对话整理完整 Phase 1 架构 |
