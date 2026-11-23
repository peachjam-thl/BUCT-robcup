# 2026-11-23 场地地图（第一份）

2026-11-23 16:00–16:17实地建图产出的第一份地图，由slam_toolbox online_async生成并取回仓库。**同日已完成首次地图重载、AMCL定位和Nav2去程/返程两次成功**，详见[导航记录](../../docs/Nav2单点导航验证.md)。本次文档同步复核了文件哈希与栅格统计，没有新增实车试验。

## 建图条件

| 项 | 值 |
| --- | --- |
| 会话目录（小车） | `/home/wheeltec/ros_field_logs/20261123_1600_map2/` |
| 建图时段 | 16:00 → 16:17（约 17 分钟） |
| 雷达 | 镭神 N10P，`/scan`，帧 `laser`，约 10 Hz |
| 里程计 | EKF 输出 `odom_combined`，20 Hz |
| 底盘入口 | 厂商 `turn_on_wheeltec_robot.launch.py`（非 D3 台架门控） |
| 遥控方式 | `wheeltec_keyboard` 键盘遥控，走手机热点 SSH |
| slam 参数 | `mapping_params.yaml`：`odom_frame=odom_combined`、`resolution=0.05`、`min_laser_range=0.2`、其余为 Humble 默认 |

## 地图指标

| 指标 | 数值 |
| --- | --- |
| 栅格尺寸 | 435 × 680 |
| 分辨率 | 0.05 m |
| 栅格画布范围（非场地实测尺寸） | 21.75 m × 34.00 m |
| 原点 | `(-9.77, -16.20, 0)` |
| 占用栅格 | 2207（0.75%） |
| 空闲栅格 | 37 299（12.61%） |
| 未知栅格 | 256 294（86.64%） |
| 已知合计 | 39 506（13.36%） |

预览中可见房间、隔断、门洞及方形障碍；实际尺寸、障碍身份仍需现场对应。外圈大片未知区与门洞外远处空间的放射状回波不应当作完整墙体。**已知13.36%是整张画布的像素比例，不是场地只完成13.36%；21.75×34m也不是房间的实测长宽。**

## 文件

| 文件 | 大小 | 说明 |
| --- | --- | --- |
| `map_20261123_1617.pgm` | 295,815 B | 占据栅格图（map_server 标准格式，0=占用 / 205=未知 / 254=空闲） |
| `map_20261123_1617.yaml` | 135 B | 元数据（分辨率 0.05、原点、阈值） |
| `map_20261123_1617.posegraph` | 18,816,920 B | 按用户要求补入的位姿图原件，与.gz解压内容逐字节一致 |
| `map_20261123_1617.posegraph.gz` | 480,691 B | 位姿图压缩后入库，配合.data用于slam_toolbox恢复 |
| `map_20261123_1617.data` | 808,048 B | 位姿图配套数据 |
| `preview.png` | 17,892 B | 渲染预览 |
| `localization-overlay.png` | 20,199 B | 重载地图后激光落点叠加（红点=激光，蓝圈=机器人） |
| `localization-pose.json` | 109 B | 本次扫描匹配的历史初值，不作后续启动通用坐标 |

SHA256（与小车原始文件逐字节一致）：

```text
pgm  adeccf206d56ee299aaee5baeb86c586dcc6775cea632fc7f1c995d90eb04fdc
yaml fc790e14bc08a5e55cbc214870e62f21dc4185fed59e735d5300b539a7746704
data 07dd9db0289340c5a9bd5e438fe24169c16e1f16d011edf45726776247695fe3
posegraph cc3297e3656a7e4badc91f218a59fc83423bd2c4380183c464023bf1a943426b
```

## 怎么用

用 `map_server` / Nav2 加载（只需要 pgm + yaml）：

```bash
ros2 run nav2_map_server map_server --ros-args -p yaml_filename:=$HOME/maps/2026-11-23/map_20261123_1617.yaml
```

仓库现已同时提供位姿图原件和压缩版。完整下载时直接使用`.posegraph`与同目录`.data`，无需解压；只下载压缩版时，在原件不存在的目录解压，避免覆盖已有原件。使用slam_toolbox恢复时，deserialize_map指定不带扩展名的前缀：

```bash
if [ ! -f map_20261123_1617.posegraph ]; then
  gunzip -k map_20261123_1617.posegraph.gz
fi
ros2 service call /slam_toolbox/deserialize_map slam_toolbox/srv/DeserializePoseGraph \
  "{filename: '$HOME/maps/2026-11-23/map_20261123_1617', match_type: 2}"
```

## 重载与定位验证（2026-11-23 16:40）

同一台车上已用 `nav2_map_server` 重新加载本图、用 `nav2_amcl`（厂商 `param_mini_mec.yaml`，`odom_frame_id=odom_combined`）完成定位：

| 指标 | 结果 |
| --- | --- |
| 地图加载 | 435 × 680 @ 0.05 m，configure/activate 成功 |
| 初始位姿 | 扫描匹配修正后 (0.387, −0.151, 19.3°) |
| 激光命中占用栅格（≤0.15 m） | **88.3%**（309 点中 273 点） |
| 到最近占用栅格距离 | 中位数 0.05 m（1 栅格） |
| AMCL `/amcl_pose` | (0.384, −0.148)，与设定一致 |

证据：[localization-overlay.png](localization-overlay.png)（红点为激光在map下的落点，蓝圈为机器人位置）、[localization-pose.json](localization-pose.json)。88.3%的分母为该快照中纳入统计且在地图内的有效激光点，0.15m为命中容差；中位0.05m是到占用栅格的量化距离，不是绝对定位误差。该工具使用最新可查TF，不代替运动过程中的严格扫描时间配准或连续定位验收。

- 初始位姿若用建图停机前的 SLAM 位姿（0.204, −0.240, 42.5°），命中率只有 25.6%，说明该位姿与地图不自洽（相差约 23°）。
- 用栅格暴力搜索得到 (0.387, −0.151, 19.3°) 后命中率升到 84–88%。**实操不要直接复用上次的位姿**，应在 RViz 里用 2D Pose Estimate 或扫描匹配重新给初值。

## 已知限制

- 原件来自本机`tmp/field-2026-11-23/map_20261123_1617.posegraph`，归档时复核SHA256与上方记录一致，且与既有.gz解压内容相同；本次补档没有产生新地图或增加实车验收。

- 地图未裁剪，画布外围86.64%是未知区。裁剪按需要另存版本，并同步调整YAML的origin和版本引用、复核定位；保留原图，不把裁剪列为继续验证的必做前置。
- 外圈放射状射线是门洞外的远距离回波，不是墙体。
- 建图中途系统时间从 2000-01-01 跳到 2026-11-23，slam 曾因此丢帧，已在 16:00 重启后重建；本图来自重启后的干净会话。
- 首次重载定位与两次单点导航已有记录；跨冷启动、多初始姿态、门洞/障碍等仍未验收。环路闭合质量和卷尺尺度对照未做，不以已有功能结果补勾。
