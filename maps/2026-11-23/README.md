# 2026-11-23 场地地图（第一份）

2026-11-23 16:00–16:17 实地建图产出的第一份可用地图。数据由 `slam_toolbox`（`online_async`）在车上生成，保存后取回本仓库。

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
| 覆盖范围 | 21.75 m × 34.00 m |
| 原点 | `(-9.77, -16.20, 0)` |
| 占用栅格 | 2207（0.75%） |
| 空闲栅格 | 37 299（12.61%） |
| 未知栅格 | 256 294（86.64%） |
| 已知合计 | 39 506（13.36%） |

地图整体是一个约 10 × 8 m 的房间，内部有隔断与门洞，可见两处方形障碍（桌/箱）。**外圈大片未知 + 放射状射线**是门洞外远处空间被扫到的结果，不是墙体；室内导航用不到，但 RViz / 路径规划时要认得出来。

## 文件

| 文件 | 大小 | 说明 |
| --- | --- | --- |
| `map_20261123_1617.pgm` | 292 KB | 占据栅格图（map_server 标准格式，0=占用 / 205=未知 / 254=空闲） |
| `map_20261123_1617.yaml` | 135 B | 元数据（分辨率 0.05、原点、阈值） |
| `map_20261123_1617.posegraph.gz` | 480 KB | 位姿图（原始 18.8 MB，压缩后入库），用于 slam_toolbox 定位模式恢复 |
| `map_20261123_1617.data` | 792 KB | 位姿图配套数据 |
| `preview.png` | 18 KB | 渲染预览 |

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

用 slam_toolbox 定位模式恢复位姿图时，先把 `posegraph.gz` 解压成同名 `.posegraph`，与 `.data` 放在同一目录，再用 `deserialize_map` 服务指定该前缀（不带扩展名）：

```bash
gunzip -k map_20261123_1617.posegraph.gz
ros2 service call /slam_toolbox/deserialize_map slam_toolbox/srv/DeserializePoseGraph \
  "{filename: '$HOME/maps/2026-11-23/map_20261123_1617', match_type: 2}"
```

## 已知限制

- 地图未裁剪，外围 86.64% 是未知区；若影响 Nav2 的全局代价地图，可以按房间边界裁一刀再发布。
- 外圈放射状射线是门洞外的远距离回波，不是墙体。
- 建图中途系统时间从 2000-01-01 跳到 2026-11-23，slam 曾因此丢帧，已在 16:00 重启后重建；本图来自重启后的干净会话。
- 本次未做环路闭合质量评估、未与卷尺实测对照、未验证重载定位。
