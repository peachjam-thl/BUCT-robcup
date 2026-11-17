# Windows 通过 USB 直连 RDK X5 并登录 SSH

更新日期：2026-11-17。USB 登录流程已由用户在自己的整车与 Windows 电脑上完成；11 月 17 日又通过小车 shell 完成 Wi-Fi 与基础外网验证。证据来自用户提供的截图和终端文字，账户密码不入库。

## 已完成的结果

| 检查项 | 已观察结果 |
| --- | --- |
| 小车用户名 / 主机名 | 本机终端为 `wheeltec@wheeltec` |
| 系统 | Ubuntu 22.04.5 LTS，jammy |
| 内核与架构 | SSH 欢迎信息显示 `GNU/Linux 6.1.83 aarch64` |
| ROS 发行版 | 本机终端执行 `printenv ROS_DISTRO` 返回 `humble`；新 SSH 会话中的环境仍待核对 |
| 小车 USB 网络地址 | `192.168.128.10` |
| Windows ping 测试 | 发送 4，接收 4，丢失 0，显示延迟 <1 ms，TTL=64；这是一次测试，不代表长期链路指标 |
| SSH | `ssh wheeltec@192.168.128.10` 成功，出现 Ubuntu 欢迎信息 |
| Wi-Fi / 互联网 | 2026-11-17 已连接，wlan0 为 192.168.1.105/24；域名解析和外网 ping 3/3 通过，详见 Wi-Fi 恢复文档 |

## 1. 接线

保持小车原有供电，用支持数据传输的 USB 线连接电脑和 X5 的 USB Device 数据口。标准 X5 官方图中数据口为 ③（USB2），供电口为 ①（PWR），Micro-USB 调试口为 ④。不同板型需按实际丝印核对，不把供电口、普通 USB-A 主机口和数据口混用。

之前照片中的 WHEELTEC `USB SOUND` 设备是 USB 声卡，不是电脑远程登录接口。

参考：[X5 官方硬件接口说明](https://developer.d-robotics.cc/rdk_x_doc/Quick_start/hardware_introduction/rdk_x5)、[官方远程登录与 USB 网络地址](https://developer.d-robotics.cc/rdk_x_doc/Quick_start/remote_login)。

## 2. Windows USB 网卡配置

按 Win+R，输入 `ncpa.cpl`。找到插线后出现的 USB 网络适配器，名称可能含 USB Ethernet、RNDIS 或“以太网 2”，以实际设备为准。

进入该网卡的“属性 → Internet 协议版本 4（TCP/IPv4）”，配置：

| 项目 | 本流程建议值 |
| --- | --- |
| 电脑 USB 网卡 IPv4 | `192.168.128.100` |
| 子网掩码 | `255.255.255.0` |
| 默认网关 | 留空 |
| DNS | 留空 |

该值为会话中给出的电脑配置步骤；用户截图未单独展示 Windows 网卡属性，因此不将电脑实际地址写成已测事实。只修改新增的 USB 网卡，不改电脑原有上网网卡。小车地址变化后，相应调整同网段配置。

## 3. 验证与登录

在 Windows PowerShell 执行：

```powershell
ping 192.168.128.10
ssh wheeltec@192.168.128.10
```

首次连接若要求确认主机，确认连接的是自己的小车后接受。输入小车 `wheeltec` 账户密码；输入时不会显示文字或星号。

本次曾出现 `Permission denied (publickey,password)`，随后使用有效账户凭据成功登录。前一次失败发生在身份认证阶段；后续成功说明本次 USB 连通和 SSH 登录目标已经完成。实际密码及任何凭据不写进仓库。

成功登录后在 SSH 会话中输入的 Linux 命令运行在小车上。退出会话用 `exit`。

## 4. 早期联网诊断及后续结果

已有本机输出：

- `nmcli device status` 显示 `wlan0` 为 `unavailable`。
- `rfkill list` 显示无线的 Soft blocked / Hard blocked 均为 `no`。
- `systemctl is-active hostapd` 返回 `inactive`。这仅说明该 systemd 服务当时未处于 active，不能据此排除手动启动的进程或其他网络配置。

早期要求在已登录的小车 SSH 会话采集：

```bash
nmcli -f GENERAL.STATE,GENERAL.REASON device show wlan0
iw dev
systemctl is-active wpa_supplicant
```

2026-11-17 已收到对应诊断：驱动为 aicwf_sdio，无固件缺失标记，接口当时为 AP 模式；wpa_supplicant 运行，但启动时间晚于 NetworkManager 放弃重试的时间。随后给出重启 NetworkManager 的建议，用户成功激活目标 Wi-Fi。完整过程与验证结果见 [Wi-Fi 恢复与联网验证](WiFi恢复与联网验证.md)。本次没有卸载无线驱动的执行记录。

后续检查清单：

```bash
date
timedatectl status
printenv ROS_DISTRO
ros2 node list
ros2 topic list -t
ls ~
```

其中 date 已于 2026-11-17 验证为正确日期；timedatectl、SSH ROS 环境、节点、Topic 和目录输出仍待采集。桌面“ROS2 V3.5(humble)”标识不能直接认定为 RDK OS 或 TROS 的准确版本。

USB SSH 本身只提供电脑与小车的连接。本次小车外网访问经另行连接 Wi-Fi 并测试得到验证，不是通过 USB 网络共享实现的。
