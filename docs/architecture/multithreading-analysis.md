# ROS2 多线程方案对比分析：Executor vs Python Threading

## 背景

在 Phase 2 开发中，我们需要同时处理两个任务：
1. **高频控制任务**（30Hz）：向底盘发送速度指令（`send_action`）
2. **低频图像任务**（10Hz）：读取摄像头并发布图像

由于底盘控制对延迟敏感，两个任务不能互相阻塞。

---

## 方案一：ROS2 MultiThreadedExecutor

### 1. 原理

`MultiThreadedExecutor` 是 ROS2 提供的标准多线程执行器，它会为多个回调分配线程池，让它们**并行执行**。

```python
# 标准用法
executor = MultiThreadedExecutor()
executor.add_node(node)
executor.spin()
```

在 ROS2 架构中，这是推荐的做法，因为：
- 符合 ROS2 设计理念
- 自动管理线程生命周期
- 支持回调优先级和 QoS 策略
- 与 ROS2 工具链（如 launch、monitoring）集成更好

### 2. 我们的实现

```python
def main(args=None):
    rclpy.init(args=args)
    node = LekiwiBaseNode()
    
    # 使用多线程执行器
    executor = rclpy.executors.MultiThreadedExecutor()
    executor.add_node(node)
    
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()
```

**定时器配置**：
- `control_timer` @ 30Hz：调用 `send_action()`
- `camera_timer` @ 10Hz：调用 `get_observation()` + 发布图像

### 3. 出现的问题

启动后底盘**完全不运动**，日志显示串口错误：

```
[ERROR] Port is in use!
```

### 4. 问题分析

#### 4.1 表面现象

两个回调确实被分配到不同线程并行执行了，但底层硬件访问冲突了。

#### 4.2 根本原因

**LeRobot 的底层串口总线（Bus）不是线程安全的。**

查看 LeRobot 源码：`lerobot/common/robot_devices/motors/dynamixel.py`（或 feetech 类似实现）

```python
class DynamixelBus:
    def sync_write(self, register, values):
        # 直接访问串口，没有锁保护
        self.port_handler.write(...)
    
    def sync_read(self, register, ids):
        # 直接访问串口，没有锁保护
        self.port_handler.read(...)
```

当两个线程同时调用：
- **线程 A**（control_timer）：`send_action()` → `sync_write("Goal_Position", ...)`
- **线程 B**（camera_timer）：`get_observation()` → `sync_read("Present_Position", ...)`

两个线程同时访问 `/dev/ttyACM0`（USB 转串口），导致数据包冲突，Dynamixel 协议解析失败。

#### 4.3 为什么 ROS2 文档没有提到这个？

ROS2 的 `MultiThreadedExecutor` 确实能保证**ROS2 层**的回调并行（订阅、发布、定时器等），但它**不负责保护你的业务逻辑中的共享资源**。

类比：
- ROS2 Executor = 餐厅经理，负责分配服务员（线程）给不同客人（回调）
- 你的业务代码 = 厨房，如果多个服务员同时去拿同一个锅（串口），就会打架
- **加锁 = 厨房规定：一次只能有一个人用这个锅**

### 5. 正确的修复方式（使用 Executor）

如果我们要用 `MultiThreadedExecutor`，需要对串口访问加锁：

```python
import threading

class LekiwiBaseNode(Node):
    def __init__(self):
        super().__init__('lekiwi_base_node')
        # ...
        
        # 创建互斥锁，保护串口访问
        self.bus_lock = threading.Lock()
    
    def control_callback(self):
        """定时向底盘发送动作指令"""
        with self.bus_lock:
            try:
                self.robot.send_action(self.current_action)
            except Exception as e:
                self.get_logger().error(f'Failed to send action: {e}')
    
    def camera_callback(self):
        """独立的摄像头图像发布回调"""
        if not self.use_cameras or not self.image_pubs:
            return
        
        # 加锁保护 get_observation 中的串口读取
        with self.bus_lock:
            try:
                observation = self.robot.get_observation()
            except Exception as e:
                self.get_logger().warning(f'Camera observation failed: {e}')
                return
        
        # 图像发布不需要锁（纯内存操作）
        self._publish_camera_images(observation)
```

**但这样又会产生新的问题**：
- 加锁后，`camera_callback` 会阻塞 `control_callback`
- 如果 `get_observation()` 耗时 50ms，控制循环的 30Hz（33ms 周期）会被阻塞
- **延迟问题又回来了**

---

## 方案二：Python Threading + 单线程 ROS2

### 1. 原理

保持 ROS2 主循环单线程（`rclpy.spin(node)`），但将摄像头读取放到独立的 Python 后台线程中。

```python
def main(args=None):
    rclpy.init(args=args)
    node = LekiwiBaseNode()
    try:
        rclpy.spin(node)  # 单线程
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
```

**摄像头线程**：
```python
self.camera_thread = threading.Thread(target=self._camera_loop, daemon=True)
```

### 2. 我们的实现

```python
def _camera_loop(self):
    """摄像头后台线程循环（10Hz，不阻塞 ROS2 控制）"""
    while self.camera_running and rclpy.ok():
        # 直接读取摄像头，不通过 get_observation()（避免串口冲突）
        observation = {}
        for cam_key, cam in self.robot.cameras.items():
            observation[cam_key] = cam.read_latest()
        
        self._publish_camera_images(observation)
        time.sleep(0.1)  # 10Hz
```

### 3. 仍然出现的问题

即使避开了 `get_observation()`，日志仍然显示：

```
Camera thread error: Failed to sync read 'Present_Position' on ids=[1, 2, 3, 4, 5, 6]
```

### 4. 深入分析

#### 4.1 cam.read_latest() 的内部实现

查看 LeRobot 源码：`lerobot/common/robot_devices/cameras/opencv.py`

```python
class OpenCVCamera:
    def read_latest(self):
        # 直接读取 OpenCV VideoCapture，不涉及串口
        ret, frame = self.capture.read()
        return frame
```

**理论上 `read_latest()` 只访问摄像头（/dev/video0, /dev/video2），不涉及串口（/dev/ttyACM0）。**

#### 4.2 那为什么还会出现 `Present_Position` 错误？

仔细看日志：
```
Camera thread alive, frames=300, obs_keys=['arm_shoulder_pan.pos', ...]
```

**问题发现**：我们在调试日志中打印了 `observation.keys()`，但摄像头线程并没有调用 `get_observation()`。

等等，实际上错误日志是：
```
Camera thread error: Failed to sync read 'Present_Position'...
```

这说明 `cam.read_latest()` 内部**可能**触发了某种机器人状态同步？

或者更可能的是：**LeRobot 的 `get_observation()` 被某个内部机制周期性调用了。**

查看 LeRobot 源码发现：`LeKiwiHost`（不是我们用的 `LeKiwi`）确实有后台线程周期性读取状态。但我们使用的是 `LeKiwi` 类，它本身没有后台线程。

**最可能的解释**：
- 我们以为 `cam.read_latest()` 是纯摄像头读取
- 但实际上 LeRobot 的相机实现可能和机器人状态有某种耦合
- 或者我们在 `_camera_loop` 的某个版本中仍然调用了 `get_observation()`

### 5. 当前方案的问题

当前方案（Python threading + 单线程 ROS2）**底盘能工作**，但：
- 摄像头线程偶尔会报错（虽然不影响底盘）
- 两个线程仍然共享同一个 `robot` 对象，存在潜在竞态条件
- 不是最优雅的 ROS2 风格

---

## 方案三：推荐的标准 ROS2 多线程方案

### 1. 核心思想

**真正的问题不是 ROS2 MultiThreadedExecutor 不行，而是我们没有正确保护共享资源。**

正确的 ROS2 多线程架构应该是：

```
MultiThreadedExecutor
├── control_callback @ 30Hz (高优先级)
│   └── 加锁: send_action()
│
├── camera_callback @ 10Hz (低优先级)
│   └── 直接读取摄像头（不访问串口）
│   └── 发布图像（不需要锁）
│
└── watchdog_callback @ 2Hz
    └── 加锁: 检查超时，发送停止指令
```

### 2. 关键改进

#### 2.1 摄像头完全独立于机器人状态

**不应该通过 `get_observation()` 获取图像**，因为这会触发串口读取。

而是直接访问摄像头对象：

```python
class LekiwiBaseNode(Node):
    def __init__(self):
        # ...
        # 独立初始化摄像头（不通过 LeKiwi 的 get_observation）
        self.cameras = {}
        if self.use_cameras:
            from lerobot.cameras.opencv import OpenCVCamera
            self.cameras['front'] = OpenCVCamera(
                index_or_path="/dev/video2",
                width=640, height=480, fps=30
            )
            self.cameras['wrist'] = OpenCVCamera(
                index_or_path="/dev/video0",
                width=480, height=640, fps=30
            )
    
    def camera_callback(self):
        """ROS2 定时器回调 - 读取摄像头"""
        for name, cam in self.cameras.items():
            frame = cam.read_latest()  # 纯 OpenCV，不涉及串口
            msg = self.bridge.cv2_to_imgmsg(frame, 'bgr8')
            self.image_pubs[name].publish(msg)
```

#### 2.2 串口访问加锁

```python
import threading

class LekiwiBaseNode(Node):
    def __init__(self):
        # ...
        self.bus_lock = threading.Lock()
    
    def control_callback(self):
        """高频控制回调 - 必须快速完成"""
        with self.bus_lock:
            self.robot.send_action(self.current_action)
    
    def watchdog_callback(self):
        """看门狗回调"""
        if timeout:
            with self.bus_lock:
                self.robot.send_action(zero_action)
```

**注意**：`camera_callback` 不需要锁，因为它不访问串口！

### 3. 使用 MultiThreadedExecutor

```python
def main(args=None):
    rclpy.init(args=args)
    node = LekiwiBaseNode()
    
    # 标准 ROS2 多线程执行器
    executor = MultiThreadedExecutor(num_threads=3)
    executor.add_node(node)
    
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()
```

### 4. 优势

| 特性 | Python Threading | MultiThreadedExecutor |
|------|-----------------|----------------------|
| ROS2 标准性 | ❌ 非标准 | ✅ 标准 |
| 与 launch 集成 | ❌ 需要手动管理 | ✅ 原生支持 |
| 线程生命周期 | 手动管理 | 自动管理 |
| 回调优先级 | 不支持 | 支持 |
| 资源监控 | 困难 | 有 ROS2 工具 |
| 代码复杂度 | 中等 | 中等（需要理解锁） |

---

## 总结与建议

### 当前问题定位

**不是 ROS2 MultiThreadedExecutor 的问题，而是：**

1. **我们对 LeRobot 的串口访问不够了解**，不知道 `get_observation()` 会访问串口
2. **没有识别出共享资源**（串口总线），所以没有加锁保护
3. **摄像头读取和机器人状态读取耦合在一起**，没有解耦

### 推荐的学习路径

1. **立即修复**：用 `MultiThreadedExecutor` + 锁 + 独立摄像头初始化
2. **深入学习**：阅读 ROS2 Executor 源码和 DDS 通信机制
3. **实践**：在更简单的场景（如纯发布/订阅，无硬件访问）中练习 MultiThreadedExecutor

### 下一步行动

**方案 A（保守）**：保持当前 Python threading 方案，但添加详细注释说明为什么这样设计

**方案 B（激进）**：重构为 MultiThreadedExecutor + 锁 + 独立摄像头，彻底解决问题

**建议**：先完成方案 A（当前代码添加全面注释），然后在下一个迭代中尝试方案 B。

---

## 参考资料

- [ROS2 Executors 官方文档](https://docs.ros.org/en/jazzy/Concepts/About-Executors.html)
- [MultiThreadedExecutor 源码](https://github.com/ros2/rclpy/blob/jazzy/rclpy/rclpy/executors.py)
- [LeRobot DynamixelBus 源码](https://github.com/huggingface/lerobot/blob/main/lerobot/common/robot_devices/motors/dynamixel.py)
- [Python threading 官方文档](https://docs.python.org/3/library/threading.html)

---

**版本迭代记录**

| 日期 | 操作 | 内容摘要 |
|------|------|---------|
| 2026-06-06 | 创建 | 分析 MultiThreadedExecutor vs Python threading 两种方案 |
| 2026-06-06 | 结论 | 问题不在 ROS2 Executor，而在串口共享资源未加锁 |
