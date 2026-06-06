# ROS2 Topic 调试技巧

## 问题

`ros2 topic echo` 刷新频率太高（通常 50Hz+），数据刷屏看不清，无法确认手柄按键是否生效。

## 解决方案：变化检测监视器

使用 `tools/topic_monitor.py` 只打印**变化的数据**，而不是每秒 50 次全部打印。

## 使用方法

### 1. 监视手柄输入（/joy）

```powershell
# 终端 1：启动手柄节点
ros2 run joy joy_node

# 终端 2：只显示变化
cd D:\work\lerobot-workspace\lerobot-ros2\tools
python topic_monitor.py /joy
```

输出效果：
```
[Button 0] 按下
[Button 0] 释放
[Axis 7] 1.000
[Axis 7] 0.000
```

### 2. 监视底盘指令（/cmd_vel）

```powershell
# 监视速度指令变化
python topic_monitor.py /cmd_vel
```

输出效果：
```
cmd_vel: x=0.50, y=0.00, θ=0.00
cmd_vel: x=0.00, y=-0.50, θ=0.00
```

## 原理

- 缓存上一次状态
- 对比新值，只在变化时打印
- 轴使用阈值（0.1）避免抖动误报
- 按钮使用精确对比

## 适用场景

| 场景 | 推荐工具 |
|------|---------|
| 快速验证手柄映射 | `topic_monitor.py /joy` |
| 验证速度指令 | `topic_monitor.py /cmd_vel` |
| 查看完整数据流 | `ros2 topic echo` |
| 记录数据到文件 | `ros2 topic echo > log.txt` |

## 相关工具

- `tools/test_gamepad.py` - 纯 pygame 手柄测试（不依赖 ROS2）
- `tools/test_joy_no_mapping.py` - 测试 joy_node 是否需要 mapping

---

**版本迭代记录**

| 日期 | 操作 | 内容摘要 |
|------|------|---------|
| 2026-06-06 | 创建 | 记录 topic 调试技巧，整理 tools 目录 |
