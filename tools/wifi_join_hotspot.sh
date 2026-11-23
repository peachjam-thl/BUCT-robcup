#!/usr/bin/env bash
# 让小车退出热点(AP)模式，改为连接指定 Wi-Fi（手机热点 / 路由器）。
# 用法：sudo bash wifi_join_hotspot.sh "热点名称"
# Wi-Fi 密码由 nmcli 交互提示输入，不写进命令历史、不写进仓库。
set -u

if [ "$(id -u)" -ne 0 ]; then
    echo "请用 sudo 运行：sudo bash $0 \"热点名称\"" >&2
    exit 1
fi

SSID="${1:-}"
if [ -z "$SSID" ]; then
    echo "缺少参数。用法：sudo bash $0 \"热点名称\"" >&2
    exit 1
fi

echo "[1/6] 停掉 AP 与 DHCP 服务"
pkill -x hostapd 2>/dev/null || true
systemctl stop isc-dhcp-server 2>/dev/null || true

echo "[2/6] 清掉 AP 地址，交回 NetworkManager"
ip addr flush dev wlan0 2>/dev/null || true
nmcli device set wlan0 managed yes 2>/dev/null || true
systemctl start wpa_supplicant 2>/dev/null || true
systemctl restart NetworkManager 2>/dev/null || true
sleep 4

echo "[3/6] 扫描附近热点"
nmcli device wifi rescan ifname wlan0 2>/dev/null || true
sleep 4
nmcli -f SSID,SIGNAL,SECURITY device wifi list ifname wlan0 2>/dev/null | head -14

echo "[4/6] 连接：$SSID（下面会提示输入 Wi-Fi 密码）"
if ! nmcli --ask device wifi connect "$SSID" ifname wlan0; then
    echo "连接失败：确认热点已开启、SSID 拼写正确、密码正确。" >&2
    exit 1
fi

echo "[5/6] 等待 DHCP"
sleep 4

echo "[6/6] 结果"
nmcli -f GENERAL.CONNECTION,IP4.ADDRESS,IP4.GATEWAY device show wlan0 2>/dev/null
ip -br addr show wlan0
GW=$(ip route 2>/dev/null | awk '/^default/{print $3; exit}')
[ -n "$GW" ] && ping -c1 -W2 "$GW" >/dev/null 2>&1 && echo "网关 $GW 可达" || echo "网关未验证"
echo
echo "把这个地址记下来，电脑连同一个热点后：ssh wheeltec@<上面的地址>"
