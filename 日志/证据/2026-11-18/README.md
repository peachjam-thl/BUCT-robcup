# 2026-11-18 原始证据

来源：Windows 通过 USB 网络（`192.168.128.10`）SSH 登录 RDK X5，四轮架空；底盘用 `ros2 launch turn_on_wheeltec_robot base_serial.launch.py` 启动，`/odom` 约 19.96 Hz。测试工具为 [tools/base_forward_probe.py](../../../tools/base_forward_probe.py) 与 [tools/cmd_vel_watchdog.py](../../../tools/cmd_vel_watchdog.py)。

| 文件 | 内容 | 结论 |
| --- | --- | --- |
| `yaw-1118.csv` / `.md` | yaw 0.15 rad/s、3 s（第一次） | wz 峰值 0.239，结束归零 |
| `silence-1118.csv` / `.md` | x 0.05 m/s、断流窗口 1.5 s | `SILENCE_STOP_NOT_OBSERVED` |
| `silence3-1118.csv` / `.md` | 同上，窗口 3.0 s | `SILENCE_STOP_NOT_OBSERVED` |
| `silence5-1118.csv` / `.md` | 同上，窗口 5.0 s | `SILENCE_STOP_NOT_OBSERVED` |
| `silence5b-1118.csv` / `.md` | 同上，工具补充逐 0.25 s 记录后复跑 | 静默段 vx 0.050→0.048，持续 4.92 s |
| `silence_wd-1118.csv` / `.md` | 同上，但看门狗在跑、探针加 `--watchdog` | `SILENCE_STOP_OBSERVED`，约 0.96 s |
| `watchdog-1118.txt` | 看门狗 ROS 日志 | `WATCHDOG_START` / `WATCHDOG_STOP` / `WATCHDOG_RELEASE` |
| [d3-gate-x-1118-1.csv](d3-gate-x-1118-1.csv) / [.md](d3-gate-x-1118-1.md) | 新分离式门控x轴架空复测；板端原文件经用户SCP取回 | 0.986s近零，操作者确认兜底前停转；随后状态DISARMED/COMMAND_TIMEOUT |
| [d3-gate-x-1118-1-终端转录.md](d3-gate-x-1118-1-终端转录.md) | 会话转录、来源和核对说明 | 224行原始数据已检查；锁定态与恢复结果见后两行 |
| [d3-disarmed-1118-1.csv](d3-disarmed-1118-1.csv) / [.md](d3-disarmed-1118-1.md) | 未重新授权请求，204行CSV已检查 | 请求阶段vx全零，请求前后状态均锁定，最终目视静止；全程目视待补 |
| [d3-rearm-x-1118-1.csv](d3-rearm-x-1118-1.csv) / [.md](d3-rearm-x-1118-1.md) | 手动重授权恢复，219行CSV已检查 | 有运动反馈；约1.033s近零，操作者确认兜底前停转，随后再次锁定 |

CSV 列：`t_s,phase,command,odom_vx,odom_vy,odom_wz`；`phase` 含 `zero_before`、`motion`、`silence`、`zero_after`，`silence` 行是停发指令后的反馈采样。`.md` 文件是脚本当次打印的证据块。

silence段command=0是探针记录占位，不代表探针发了零速，也不是门控输出记录。旧1118批次时钟为2000年；新D3文件显示2026-11-18，RTC/NTP及重启保持仍未验证。

判读与结论见 [2026-11-18 日志](../../2026-11-18.md)；看门狗行为见 [指令看门狗](../../../docs/指令看门狗.md)。

**时间戳注意：** 旧批次板端时钟为`2000-01-01`，不能当作真实日期；新D3三轮文件显示2026-11-18。运行中同步曾通过，重启后RTC又回2000，保持未通过。相对时间仅用于对应场景内估计，不等于精确制动测量。

本目录不含密码、密钥、Wi-Fi名称或令牌。旧批次的补充目视写在日志正文；新D3证据块包含操作员回答，缺失项仍标为未记录。
