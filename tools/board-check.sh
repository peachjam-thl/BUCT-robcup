#!/usr/bin/env bash
# 板端只读体检脚本（RDK X5 / Ubuntu 22.04 / ROS 2 Humble）
#
# 用途：一次性收集排查 Wi-Fi 与 ROS 现状所需的输出，不修改任何配置，不需要 root。
# 用法一（Windows 电脑，USB 已连好，推荐）：
#   Get-Content .\tools\board-check.sh -Raw | ssh wheeltec@192.168.128.10 'bash -s'
# 用法二（板卡本机终端）：
#   bash ~/board-check.sh
# 把整段输出发回即可；若内容太长，可 > board-check.txt 2>&1 保存后传回。

set +e
export LC_ALL=C
export TERM=dumb

SEC=0
sec() { SEC=$((SEC + 1)); printf '\n\n########## %d. %s ##########\n' "$SEC" "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }
say() { printf '\n$ %s\n' "$*"; }

printf '板端体检开始: %s\n' "$(date '+%F %T %Z')"
printf '主机名: %s  用户: %s\n' "$(hostname)" "$(id -un)"

sec "时间与时区"
say "date"
date 2>&1
say "timedatectl status"
have timedatectl && timedatectl status 2>&1

sec "系统与内核"
say "uname -a"
uname -a 2>&1
say "cat /etc/os-release"
cat /etc/os-release 2>&1
say "机型"
cat /proc/device-tree/model 2>/dev/null; echo

sec "网络接口"
say "ip -br addr"
ip -br addr 2>&1
say "ip -br link"
ip -br link 2>&1

sec "NetworkManager 状态"
say "nmcli device status"
have nmcli && nmcli device status 2>&1
say "nmcli -f GENERAL.STATE,GENERAL.REASON,GENERAL.HWADDR,IP4.ADDRESS device show wlan0"
have nmcli && nmcli -f GENERAL.STATE,GENERAL.REASON,GENERAL.HWADDR device show wlan0 2>&1
say "nmcli radio"
have nmcli && nmcli radio 2>&1
say "nmcli connection show"
have nmcli && nmcli connection show 2>&1

sec "无线内核层"
say "iw dev"
have iw && iw dev 2>&1
say "iw list 中支持的接口模式"
have iw && iw list 2>/dev/null | grep -A6 -i 'Supported interface modes' | head -n 12
say "rfkill list"
have rfkill && rfkill list 2>&1

sec "相关服务"
for s in NetworkManager wpa_supplicant hostapd dnsmasq systemd-resolved; do
  if systemctl list-unit-files 2>/dev/null | grep -q "^${s}\.service"; then
    printf '%-20s enabled=%s active=%s\n' "$s" \
      "$(systemctl is-enabled "$s" 2>&1)" "$(systemctl is-active "$s" 2>&1)"
  else
    printf '%-20s (无此单元)\n' "$s"
  fi
done
say "systemctl --failed --no-pager"
systemctl --failed --no-pager 2>&1 | head -n 20

sec "驱动与固件日志"
say "lsmod | grep -iE 'aic8800|cfg80211|wlan'"
lsmod 2>/dev/null | grep -iE 'aic8800|cfg80211|wlan' || echo '(无匹配模块)'
say "dmesg 中无线相关（最后 25 行）"
dmesg 2>/dev/null | grep -iE 'aic8800|aic|wlan|firmware' | tail -n 25 || echo '(dmesg 需要权限，跳过)'

sec "网络配置来源"
for f in /etc/network/interfaces /etc/NetworkManager/NetworkManager.conf; do
  say "cat $f"
  [ -r "$f" ] && cat "$f" 2>&1 || echo '(不存在或不可读)'
done
say "ls /etc/network/interfaces.d"
ls -l /etc/network/interfaces.d 2>&1
say "ls /etc/netplan"
ls -l /etc/netplan 2>&1
say "ls /etc/NetworkManager/system-connections"
ls -l /etc/NetworkManager/system-connections 2>&1

sec "路由、DNS 与连通性"
say "ip route"
ip route 2>&1
say "ls -l /etc/resolv.conf; cat /etc/resolv.conf"
ls -l /etc/resolv.conf 2>&1; cat /etc/resolv.conf 2>&1
say "resolvectl status（前 20 行）"
have resolvectl && resolvectl status 2>&1 | head -n 20
GW=$(ip route 2>/dev/null | awk '/^default/{print $3; exit}')
if [ -n "$GW" ]; then
  say "ping 网关 $GW"
  ping -c1 -W2 "$GW" 2>&1 | tail -n 3
else
  echo; echo '$ 无默认路由，跳过网关 ping'
fi
say "ping 223.5.5.5（公网 IP）"
ping -c1 -W2 223.5.5.5 2>&1 | tail -n 3
say "ping www.baidu.com（DNS + 外网）"
ping -c1 -W2 www.baidu.com 2>&1 | tail -n 3

sec "ROS 环境"
say "env | grep -E 'ROS_|RMW_|AMENT_'"
env 2>/dev/null | grep -E 'ROS_|RMW_|AMENT_' || echo '(无 ROS 环境变量)'
say "command -v ros2"
command -v ros2 2>&1 || echo '(未找到 ros2)'
say "ls /opt 与常见环境入口"
ls /opt 2>&1
ls -d /opt/tros/*/setup.bash /opt/ros/*/setup.bash 2>/dev/null || echo '(未发现标准 setup.bash)'
say "ros2 pkg list | wc -l"
have ros2 && timeout 20 ros2 pkg list 2>/dev/null | wc -l
say "ros2 node list"
have ros2 && timeout 15 ros2 node list 2>&1
say "ros2 topic list -t（前 40 行）"
have ros2 && timeout 20 ros2 topic list -t 2>&1 | head -n 40

sec "工作空间与设备"
say "ls -la ~"
ls -la ~ 2>&1 | head -n 40
say "ls ~/Documents ~/Desktop /dev/ttyUSB* /dev/ttyACM* /dev/can*"
ls -d ~/Documents ~/Desktop 2>/dev/null
ls -l /dev/ttyUSB* /dev/ttyACM* /dev/can* 2>&1 | head -n 10
say "lsusb"
have lsusb && lsusb 2>&1

printf '\n\n########## 体检结束 %s ##########\n' "$(date '+%F %T')"
