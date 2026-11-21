# 2026-11-21 静态 TF 与关节数据实测

采集方式：本会话通过 USB 网络（`192.168.128.10`）SSH 执行，用户在场插线确认。板端时钟仍为 `2000-01-01`，文中时间只用于同一轮内的先后顺序。

起点：板子重启后 ROS 图为空（`ros2 node list` 无输出、`/tf_static` 报 unknown）。上传 [tools/vendor_model_static.launch.py](../../../tools/vendor_model_static.launch.py) 到 `/tmp` 并启动后采集。

## 原始输出

```text
### 采集时间与主机
Sat Jan  1 08:05:35 AM CST 2000
wheeltec
6.1.83

### ros2 node list
/vendor_static_base_to_laser
/vendor_static_base_to_link
/vendor_static_joint_state_publisher
/vendor_static_robot_state_publisher

### tf2_echo base_footprint laser
[INFO] [0946685139.363441165] [tf2_echo]: Waiting for transform base_footprint ->  laser: Invalid frame ID "base_footprint" passed to canTransform argument target_frame - frame does not exist
At time 0.0
- Translation: [0.032, 0.000, 0.095]
- Rotation: in Quaternion (xyzw) [0.000, 0.000, 0.000, 1.000]
- Rotation: in RPY (radian) [0.000, -0.000, 0.000]
- Rotation: in RPY (degree) [0.000, -0.000, 0.000]
- Matrix:
  1.000  0.000  0.000  0.032
  0.000  1.000  0.000  0.000
  0.000  0.000  1.000  0.095
  0.000  0.000  0.000  1.000
At time 0.0

### tf2_echo base_footprint camera_link
[INFO] [0946685142.521417035] [tf2_echo]: Waiting for transform base_footprint ->  camera_link: Invalid frame ID "base_footprint" passed to canTransform argument target_frame - frame does not exist
At time 0.0
- Translation: [0.107, 0.000, 0.076]
- Rotation: in Quaternion (xyzw) [0.000, 0.000, 0.000, 1.000]
- Rotation: in RPY (radian) [0.000, -0.000, 0.000]
- Rotation: in RPY (degree) [0.000, -0.000, 0.000]
- Matrix:
  1.000  0.000  0.000  0.107
  0.000  1.000  0.000  0.000
  0.000  0.000  1.000  0.076
  0.000  0.000  0.000  1.000
At time 0.0

### ros2 topic echo /joint_states --once
header:
  stamp:
    sec: 946685147
    nanosec: 611607561
  frame_id: ''
name:
- lf_wheel_joint
- lb_wheel_joint
- rb_wheel_joint
- rf_wheel_joint
position:
- 0.0
- 0.0
- 0.0
- 0.0
velocity: []
effort: []
---

### tf_static 发布者
Publisher count: 3
Node name: vendor_static_robot_state_publisher
Node namespace: /
Node name: vendor_static_base_to_link
Node namespace: /
Node name: vendor_static_base_to_laser
Node namespace: /
Node name: transform_listener_impl_aaaacc7a94b0
Node namespace: /
Node name: transform_listener_impl_aaaaf4fe65e0
Node namespace: /

### /tf_static 原始边
    frame_id: base_footprint
  child_frame_id: base_link
    frame_id: base_footprint
  child_frame_id: laser
    frame_id: base_link
  child_frame_id: camera_link
    frame_id: base_link
  child_frame_id: controller_link
    frame_id: base_link
  child_frame_id: laser_link
```

## 结果摘要

| 检查 | 实际输出 | 判定 |
| --- | --- | --- |
| `base_footprint→laser` | Translation `[0.032, 0.000, 0.095]`，单位四元数 | 与文件值 `0.03163 / 0.00009 / 0.09502` 一致（`tf2_echo` 只保留三位小数） |
| `base_footprint→camera_link` | Translation `[0.107, 0.000, 0.076]`，单位四元数 | 与 `0.1070947 / 0.0003171 / 0.076204` 一致 |
| `/joint_states` | 四轮关节 `lf/lb/rb/rf_wheel_joint`，`position` 全 `0.0`，`velocity`、`effort` 为空 | 收到默认显示值；不是编码器或轮速反馈 |
| `/tf_static` 发布者 | 3 个：`vendor_static_robot_state_publisher`、`vendor_static_base_to_link`、`vendor_static_base_to_laser` | 边不重复：`base_footprint→base_link`、`base_footprint→laser`、`base_link→camera_link/controller_link/laser_link` |

## 需要保留的观察

- 两次 `tf2_echo` 首行都打印 `Invalid frame ID "base_footprint" ... frame does not exist`，随后才输出变换：这是 `tf_static` 晚于查询到达的瞬态，不是查询失败，全过程已保留。
- `laser` 与 `laser_link` 同时存在不是重复发布：前者是扫描帧（`base_footprint→laser`，零旋转），后者是 URDF 子帧（`base_link→laser_link`，yaw=π）。两条边的父帧不同。
- 本轮只有静态模型，**没有 `odom→base_footprint` 动态 TF**，不能据此开始移动或建图。
- `/joint_states` 的 `position` 全为 0 只是静态显示值，不能当作轮子实际角度。
