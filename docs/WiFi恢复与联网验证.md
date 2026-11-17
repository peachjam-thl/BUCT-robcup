# Wi-Fi 恢复与联网验证

记录日期：2026-11-17。设备：当前项目的 RDK X5 自组装整车。操作由用户在小车 SSH shell 中执行，结果根据其粘贴输出整理。实际 Wi-Fi 名称、密码、无线 MAC 地址不入库。

## 已确认的结果

| 项目 | 本次结果 |
| --- | --- |
| Wi-Fi 激活 | nmcli 返回 Device 'wlan0' successfully activated |
| wlan0 IPv4 | 192.168.1.105/24 |
| 网关 | 192.168.1.1 |
| 域名解析 | www.baidu.com 成功解析为公网地址 |
| 外网 ping | 发送 3，接收 3，0% 丢包 |
| RTT min / avg / max | 6.478 / 18.032 / 39.299 ms，仅代表本次短时测试 |
| 系统日期 | Tue Nov 17 05:07:15 PM CST 2026 |

Wi-Fi 地址是本次取得的地址，换网络或后续重新分配后可能变化。尚未验证 HTTPS 下载、重启后的自动连接、RTC/NTP 同步机制，也未从 Windows 单独验证 Wi-Fi 地址上的 SSH。

## 诊断依据

早期 nmcli 显示 wlan0 unavailable，扫描列表为空。进一步输出确认：

```text
GENERAL.DRIVER:              aicwf_sdio
GENERAL.DRIVER-VERSION:      6.1.83
GENERAL.STATE:               20 (unavailable)
GENERAL.REASON:              2 (Device is now managed)
GENERAL.NM-MANAGED:          yes
GENERAL.FIRMWARE-MISSING:    no
GENERAL.NM-PLUGIN-MISSING:   no
```

`iw dev` 当时显示 `type AP` 和一个预设机器人热点名。`wpa_supplicant.service` 显示 enabled、active (running)，进程带 `-u -s -O /run/wpa_supplicant` 参数。

日志中的相对顺序为：

```text
08:00:22  Couldn't initialize supplicant interface:
          Failed to D-Bus activate wpa_supplicant service
08:01:27  supplicant interface keeps failing, giving up
08:02:29  wpa_supplicant.service 已处于 active (running)
```

这些日志当时使用的是尚未校正的系统日期，应看同一启动中的先后顺序，不把其中 2000 年当成实际操作日期。证据表明 NetworkManager 放弃重试后，wpa_supplicant 才启动成功；接口当时还在 AP 模式。随后建议重新启动 NetworkManager。用户之后提供了目标 Wi-Fi 激活及联网成功输出。

该过程支持“服务启动先后与无线接管状态有关”的判断，但没有逐项独立实验；不能宣称每台 X5 都有相同根因，也没有恢复后的 iw 输出来单独确认最终模式字段。

## 本次使用的恢复与连接流程

此前用户提供的《恢复wifi模式.txt》包含解除无线禁用、交由 NetworkManager 管理、解除 wpa_supplicant 屏蔽、重启服务等步骤。当前会话先尝试了保留 NetworkManager 运行的步骤，再依据上述日志补充重启 NetworkManager 的建议。下面为整理后的参考顺序，遇到相同症状时仍应先采集当前状态。

在小车终端或已登录的小车 SSH 会话逐条运行；某一步报错先记录，不把后续成功预设为必然：

```bash
sudo rfkill unblock wifi
sudo systemctl unmask wpa_supplicant
sudo systemctl restart wpa_supplicant
sudo nmcli device set wlan0 managed yes
sudo nmcli radio wifi on
sudo systemctl restart NetworkManager
```

重启 NetworkManager 可能暂时影响 SSH；操作前保留 USB 接线和车载终端恢复入口。若 SSH 中断，在 Windows 重新执行 `ssh wheeltec@192.168.128.10`。该过程没有要求重刷系统、卸载无线驱动或清空全部地址。

等待数秒后检查：

```bash
nmcli device status
iw dev
nmcli device wifi list ifname wlan0
```

能扫描且设备可用于连接后，连接目标网络：

```bash
sudo nmcli --ask device wifi connect "你的热点名称" ifname wlan0
```

将双引号中的名称替换为实际 SSID；sudo 提示输入小车账户密码，无线密码提示输入目标网络密码。密码只在本机交互输入，不写入命令、日志或仓库。若仍 unavailable，采集设备详情、服务状态和日志继续诊断。

参考：[NetworkManager nmcli 官方说明](https://networkmanager.dev/docs/api/latest/nmcli.html)、[systemctl 官方说明](https://www.freedesktop.org/software/systemd/man/latest/systemctl.html)。

## 用户提供的验收输出（脱敏摘录）

```text
Device 'wlan0' successfully activated with '<连接UUID略>'.
GENERAL.CONNECTION: <SSID略>
IP4.ADDRESS[1]:     192.168.1.105/24
IP4.GATEWAY:        192.168.1.1

3 packets transmitted, 3 received, 0% packet loss, time 2003ms
rtt min/avg/max/mdev = 6.478/18.032/39.299/15.056 ms

Tue Nov 17 05:07:15 PM CST 2026
```

对应验证命令：

```bash
nmcli -f GENERAL.CONNECTION,IP4.ADDRESS,IP4.GATEWAY device show wlan0
ping -c 3 www.baidu.com
date
```

## 下一次接着做

先连接已验证的 USB SSH 入口，再执行：

```bash
ls ~
ros2 node list
ros2 topic list -t
```

上述三项输出尚未收到。下一阶段先找现有工作空间、底盘/雷达/相机驱动和启动脚本，再设计运动验收。网络复测可另检查 timedatectl、HTTPS、冷启动自动连接，以及 Wi-Fi 地址上的 SSH。
