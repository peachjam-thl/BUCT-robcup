# Nav2 单点导航验证

日期：2026-11-23 16:30–16:42。基于[第一份地图](../maps/2026-11-23/README.md)进行规划、执行、到达和返回，去程/返程两次Action均成功。本次文档同步未增加试验；取消、末端朝向、异常及扩大场景仍未验收。

**接续点：D12后半的取消/停稳和短路径复现。** 先查本轮连接、domain、时基和控制链，不能由历史成功推定当前仍在运行或已安全退出。11月23日厂商底盘直接订阅`/cmd_vel`，不是D3台架门控；有人能断电属于现场措施，不是独立失联保护验收。

## 本次测试时的前提状态（不是当前在线清单）

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

随后根据当前实物位置和朝向，在RViz用2D Pose Estimate或经核查的扫描匹配结果给初值，再用[定位检查工具](../tools/localization_check.py)核对。**下列坐标仅为本次试验历史值，不是通用启动指令，车被搬动或重新放置后不能照抄。** 原因见[地图说明](../maps/2026-11-23/README.md)。

```text
本次历史初值：x=0.387 m，y=-0.151 m，yaw=19.3°
本次历史四元数：z=0.1676，w=0.9859
```

导航前确认键盘遥控未在同时发布速度，地图/定位节点没有重复；底盘、雷达已有时只起导航栈。启动片段是本次已用入口，不是自动判断运动条件已成立的脚本。

## 本次结果

| 测试 | 结果 |
| --- | --- |
| 规划（只算路不走） | `compute_path_to_pose` 成功，0.82 m / 32 个路点，起点 (0.38, −0.15) → 终点 (1.14, 0.11) |
| 第1次导航 | NavigateToPose成功（status=4），到达估计位姿(1.177,0.076)，与目标(1.14,0.11)的坐标距离约0.05m |
| 第2次导航（返回起点） | 成功（status=4），13.9s；到达估计位姿(0.527,−0.113)，与目标坐标距离约0.15m（记录的默认位置容差0.25m） |
| 定位一致性 | 到达后激光对齐命中率 **93.3%**（≤0.15 m，中位 0.000 m）；返回后 **88.8%**（中位 0.000 m） |
| AMCL | 持续输出 `/amcl_pose`，`map→odom_combined` 由 AMCL 发布，行进中未丢失 |

判定：本次地图、定位、规划、控制、底盘执行与到达停车已有两次有限成功记录。0.05/0.15m来自估计位姿与目标的坐标差，未用外部尺度测量验证真实到达误差；不能据两次结果宣称长期可靠性或整场重复成功。93.3%/88.8%是当时静止快照的地图内有效激光点对齐比例，不是导航成功率或绝对定位精度。

## 重复定位节点与地图/TF中断

第一次启动 bringup 时，之前手工起的 `map_server` / `amcl` 没被 `pkill` 杀掉（它们的进程名是绝对路径，`pkill -f 'nav2_map_server map_server'` 匹配不到），结果同名节点各起一份：

- 同一轮检查中`/map`变成0个发布者；
- `map→laser` 的 TF 直接消失，`localization_check` 报 `"map" does not exist`。

处理记录：核对对应PID后正常发送SIGINT、清理重复实例，再启动唯一一套bringup后恢复。该轮现象不能概括为“同名节点一定互相覆盖成0发布者”，具体内部触发机制未独立定位。复现前先保持车辆停止，从原终端正常退出；原终端丢失时再依据已核对的PID处理，不照抄宽泛pkill命令。

**规则：同一套 Bringup 里只能有一份 map_server / amcl。** 手动起过定位节点，就先全部停掉再交给 launch。

## 还没验证的

- 跨门洞、窄通道、家具绕行（D13）；
- 静态/低矮/移动障碍与恢复行为（D23）；
- 取消目标、失败重试、节点异常退出的处置（D12 后半、D24）；
- 长距离、多目标的累计误差；
- 下位机独立超时仍未验证——**自主运动时仍需要有人能随时断电**。

## 下次验证顺序

1. 只读核对domain10、当前时基、实际速度来源、唯一map_server/amcl和生命周期；根据当前位置给初值并核对静止对齐。
2. 确认现场停止条件及当前控制链后，在有限短路径验证取消：保存取消响应、Action最终状态、反馈速度和轮子实际停稳时序；未测前不补勾。
3. 补短路径重复、末端朝向及失败原因，再按前置条件评估多点、门洞和障碍。参数上限、footprint与原始车身文件继续核对，未完成项见[执行计划](../执行计划表.md)。
