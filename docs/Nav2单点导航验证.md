# Nav2 单点导航验证

日期：2026-11-23 16:30–16:42。基于 [第一份地图](../maps/2026-11-23/README.md) 做的首次自主导航验证：**规划 → 执行 → 到达 → 返回**，两次都成功。

## 前提状态

| 组件 | 状态 |
| --- | --- |
| 底盘 `wheeltec_robot` | 运行中，`/cmd_vel` 订阅者 |
| 雷达 `lslidar_driver_node` | 运行中，`/scan` 约 10 Hz |
| EKF | 运行中，`/odom_combined` 约 20 Hz |
| SLAM | **已停止**（定位阶段不建图） |
| 键盘遥控 | **已停止**（避免与 Nav2 抢 `/cmd_vel`） |
| 地图 | `~/maps/2026-11-23/map_20261123_1617.yaml` |

## 启动命令

只起导航栈，不重复启动底盘和雷达：

```bash
export ROS_DOMAIN_ID=10
source /opt/ros/humble/setup.bash
source ~/wheeltec_ros2/install/setup.bash
P=~/wheeltec_ros2/install/wheeltec_nav2/share/wheeltec_nav2
ros2 launch $P/launch/bringup_launch.py \
  map:=$HOME/maps/2026-11-23/map_20261123_1617.yaml \
  params_file:=$P/param/wheeltec_params/param_mini_mec.yaml \
  use_sim_time:=false autostart:=true use_composition:=False
```

`use_composition:=False` 是为了每个服务单独成节点，便于用 `ros2 lifecycle get` 逐个检查；参数用厂商 `param_mini_mec.yaml`（`Amcl`/`DWB`/`NavFn` 全在里面，`odom_frame_id=odom_combined`、`base_frame_id=base_footprint`）。

启动后确认：

```bash
ros2 topic info /map                    # 发布者应为 1
ros2 lifecycle get /map_server          # active [3]
ros2 lifecycle get /amcl                # active [3]
ros2 lifecycle get /planner_server      # active [3]
ros2 lifecycle get /controller_server   # active [3]
ros2 lifecycle get /bt_navigator        # active [3]
```

然后给初始位姿（**必须做，不能沿用上次**，原因见 [地图说明](../maps/2026-11-23/README.md)）：

```bash
ros2 topic pub --once /initialpose geometry_msgs/msg/PoseWithCovarianceStamped \
"{header: {frame_id: map}, pose: {pose: {position: {x: 0.387, y: -0.151}, orientation: {z: 0.1676, w: 0.9859}}, covariance: [0.25,0,0,0,0,0, 0,0.25,0,0,0,0, 0,0,0,0,0,0, 0,0,0,0,0,0, 0,0,0,0,0,0, 0,0,0,0,0,0.0685]}}"
```

## 本次结果

| 测试 | 结果 |
| --- | --- |
| 规划（只算路不走） | `compute_path_to_pose` 成功，0.82 m / 32 个路点，起点 (0.38, −0.15) → 终点 (1.14, 0.11) |
| 第 1 次导航 | `NavigateToPose` 成功（status=4），到达 (1.177, 0.076)，与目标 (1.14, 0.11) 误差约 **0.05 m** |
| 第 2 次导航（返回起点） | 成功（status=4），耗时约 13.9 s，停在 (0.527, −0.113)，与目标误差约 0.15 m（在默认 0.25 m 容差内） |
| 定位一致性 | 到达后激光对齐命中率 **93.3%**（≤0.15 m，中位 0.000 m）；返回后 **88.8%**（中位 0.000 m） |
| AMCL | 持续输出 `/amcl_pose`，`map→odom_combined` 由 AMCL 发布，行进中未丢失 |

判定：**地图 → 定位 → 规划 → 控制 → 底盘执行 → 到达停车** 这条链路是通的，且可重复。

## 踩到的坑：重复节点会把地图"整没"

第一次启动 bringup 时，之前手工起的 `map_server` / `amcl` 没被 `pkill` 杀掉（它们的进程名是绝对路径，`pkill -f 'nav2_map_server map_server'` 匹配不到），结果同名节点各起一份：

- `/map` 变成 **0 个发布者**（两个同名节点互相覆盖，生命周期也乱）；
- `map→laser` 的 TF 直接消失，`localization_check` 报 `"map" does not exist`。

处理：按 PID 杀干净（`kill -INT <pid> <pid>`），确认 `pgrep -a -f 'nav2_map_server|nav2_amcl'` 只剩一组，再重启 bringup。

**规则：同一套 Bringup 里只能有一份 map_server / amcl。** 手动起过定位节点，就先全部停掉再交给 launch。

## 还没验证的

- 跨门洞、窄通道、家具绕行（D13）；
- 静态/低矮/移动障碍与恢复行为（D23）；
- 取消目标、失败重试、节点异常退出的处置（D12 后半、D24）；
- 长距离、多目标的累计误差；
- 下位机独立超时仍未验证——**自主运动时仍需要有人能随时断电**。
