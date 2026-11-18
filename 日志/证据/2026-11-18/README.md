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

CSV 列：`t_s,phase,command,odom_vx,odom_vy,odom_wz`；`phase` 含 `zero_before`、`motion`、`silence`、`zero_after`，`silence` 行是停发指令后的反馈采样。`.md` 文件是脚本当次打印的证据块。

判读与结论见 [2026-11-18 日志](../../2026-11-18.md)；看门狗行为见 [指令看门狗](../../../docs/指令看门狗.md)。

**时间戳注意：** 板端时钟当时是 `2000-01-01`（RTC/NTP 未工作），文件内时间只能用于同一场景内的相对顺序，不能当作真实时刻。

本目录不含密码、密钥、Wi-Fi 名称或令牌。操作员对轮子的目视结论写在日志正文，不在这批文件里。
