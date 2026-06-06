# Phase 2: 摄像头图像传输

## 目标

在 Phase 1（底盘遥控）基础上，添加摄像头图像采集和传输功能，实现 PC 端实时查看树莓派摄像头画面。

## 架构

```
树莓派 (lekiwi-pi)
├── base_node
│   ├── 底盘控制 (/cmd_vel)
│   └── 摄像头发布 (/camera/front/image_raw, /camera/wrist/image_raw)
│
PC (Windows)
├── joy_node (手柄读取)
├── joy_to_cmd_vel (手柄→底盘指令转换)
└── image_viewer.py (OpenCV 图像显示)
```

## 实现步骤

### 1. 树莓派端：修改 base_node 添加图像发布

**文件**: `src/lekiwi_base/lekiwi_base/base_node.py`

#### 1.1 导入依赖

```python
import numpy as np
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
```

#### 1.2 初始化图像发布器

在 `__init__` 中，当 `use_cameras=True` 时创建两个发布器：

```python
self.image_pubs = {}
self.bridge = None
if self.use_cameras:
    self.bridge = CvBridge()
    # front 摄像头
    self.image_pubs['front'] = self.create_publisher(
        Image, '/camera/front/image_raw', 10
    )
    # wrist 摄像头
    self.image_pubs['wrist'] = self.create_publisher(
        Image, '/camera/wrist/image_raw', 10
    )
```

#### 1.3 配置摄像头参数

覆盖默认配置，指定正确的设备路径、分辨率、旋转角度和预热时间：

```python
config.cameras = {
    "front": OpenCVCameraConfig(
        index_or_path="/dev/video2",  # front 摄像头设备
        width=640,
        height=480,
        fps=30,
        warmup_s=3,                    # 预热 3 秒
        rotation=Cv2Rotation.ROTATE_180,
    ),
    "wrist": OpenCVCameraConfig(
        index_or_path="/dev/video0",  # wrist 摄像头设备
        width=480,
        height=640,
        fps=30,
        warmup_s=3,                    # 预热 3 秒
        rotation=Cv2Rotation.ROTATE_90,
    ),
}
```

#### 1.4 发布摄像头图像

在 `control_callback` 中，每次控制循环时读取并发布图像：

```python
def _publish_camera_images(self):
    observation = self.robot.get_observation()
    
    # 发布 front 摄像头
    if 'front' in observation:
        front_img = observation['front']
        img_msg = self.bridge.cv2_to_imgmsg(front_img, encoding='bgr8')
        img_msg.header.stamp = self.get_clock().now().to_msg()
        img_msg.header.frame_id = 'front_camera'
        self.image_pubs['front'].publish(img_msg)
    
    # 发布 wrist 摄像头
    if 'wrist' in observation:
        wrist_img = observation['wrist']
        img_msg = self.bridge.cv2_to_imgmsg(wrist_img, encoding='bgr8')
        img_msg.header.stamp = self.get_clock().now().to_msg()
        img_msg.header.frame_id = 'wrist_camera'
        self.image_pubs['wrist'].publish(img_msg)
```

### 2. PC 端：创建图像查看器

**文件**: `tools/image_viewer.py`

使用 OpenCV 显示 ROS2 图像 Topic，轻量级替代 `rqt_image_view`：

```python
class ImageViewer(Node):
    def __init__(self):
        super().__init__('image_viewer')
        self.sub = self.create_subscription(
            Image, '/camera/front/image_raw', self.image_callback, 10
        )
        self.bridge = CvBridge()
    
    def image_callback(self, msg):
        cv_image = self.bridge.imgmsg_to_cv2(msg, encoding='bgr8')
        cv2.imshow('LeKiwi Camera', cv_image)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            rclpy.shutdown()
```

## 使用方法

### 前置条件

确保 PC 和树莓派都安装了 `cv_bridge`：

```bash
# PC (Windows)
conda activate ros2
pip install cv-bridge

# 树莓派 (Ubuntu)
conda activate ros2
pip install cv-bridge
```

### 启动步骤

#### 1. 树莓派：启动底盘+摄像头节点

```bash
cd ~/lerobot-workspace/lerobot-ros2
git pull

# 重新安装
cd src/lekiwi_base
pip install -e .

# 启动（启用摄像头）
cd ~/lerobot-workspace/lerobot-ros2
python -m lekiwi_base.base_node --ros-args -p use_cameras:=true
```

#### 2. PC：启动手柄控制（Phase 1 已有）

```powershell
# 终端 1：joy_node
ros2 run joy joy_node

# 终端 2：joy_to_cmd_vel
python -m lekiwi_teleop.joy_to_cmd_vel
```

#### 3. PC：启动图像查看器

```powershell
cd D:\work\lerobot-workspace\lerobot-ros2\tools
conda activate ros2

# 查看 front 摄像头
python image_viewer.py --ros-args -p topic:=/camera/front/image_raw

# 或查看 wrist 摄像头
python image_viewer.py --ros-args -p topic:=/camera/wrist/image_raw
```

### 验证

检查 Topic 是否存在：

```powershell
ros2 topic list | findstr camera
# 输出：
# /camera/front/image_raw
# /camera/wrist/image_raw
```

检查图像发布频率：

```powershell
ros2 topic hz /camera/front/image_raw
# 约 30 Hz
```

## 摄像头配置详情

| 参数 | front | wrist |
|------|-------|-------|
| 设备路径 | `/dev/video2` | `/dev/video0` |
| 分辨率 | 640x480 | 480x640 |
| 帧率 | 30 fps | 30 fps |
| 旋转 | 180° | 90° |
| 预热时间 | 3 秒 | 3 秒 |
| ROS Topic | `/camera/front/image_raw` | `/camera/wrist/image_raw` |

## 关键设计决策

1. **ROS2 标准图像传输**
   - 使用 `sensor_msgs/Image` 消息格式
   - 通过 `cv_bridge` 进行 ROS2 ↔ OpenCV 转换
   - 符合 ROS2 图像管道标准，可与其他 ROS2 工具兼容

2. **双摄像头独立 Topic**
   - front 和 wrist 分别发布到不同 Topic
   - PC 端可独立订阅，灵活选择查看哪个视角
   - 为后续多视角算法预留接口

3. **warmup 机制**
   - 摄像头初始化后等待 3 秒，确保曝光稳定
   - 避免启动时图像过曝/欠曝

4. **OpenCV 查看器**
   - 轻量级，无需安装 `rqt`
   - 支持实时显示，按 Q 退出
   - 可在低配置 PC 上流畅运行

## 文件变更

- `src/lekiwi_base/lekiwi_base/base_node.py` - 添加图像发布逻辑
- `tools/image_viewer.py` - 新增 PC 端查看器

---

**版本迭代记录**

| 日期 | 操作 | 内容摘要 |
|------|------|---------|
| 2026-06-06 | 创建 | Phase 2 初始版本，双摄像头 ROS2 传输 |
