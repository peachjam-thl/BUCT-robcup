#!/usr/bin/env bash
# 小车 Wi-Fi 热点（AP）模式：让电脑直接连小车，不需要路由器/热点。
# 用法：  sudo bash wifi_ap_up.sh
# 还原：  sudo bash wifi_ap_down.sh
# 说明：使用镜像自带的 /etc/hostapd.conf（SSID、密码以该文件为准，改它即可换名字/密码）。
#       AP 模式下小车地址固定为 192.168.0.100，DHCP 由 isc-dhcp-server 发给电脑。
set -u

IFACE=wlan0
CONF=/etc/hostapd.conf
ADDR=192.168.0.100

if [ "$(id -u)" -ne 0 ]; then
    echo "请用 sudo 运行：sudo bash $0" >&2
    exit 1
fi

if [ ! -f "$CONF" ]; then
    echo "缺少 $CONF，无法启动热点" >&2
    exit 1
fi
SSID=$(grep -m1 '^ssid=' "$CONF" | cut -d= -f2)

echo "[1/6] 让 NetworkManager 放开 $IFACE"
nmcli device set "$IFACE" managed no 2>/dev/null || true

echo "[2/6] 停止客户端 supplicant"
systemctl stop wpa_supplicant 2>/dev/null || true

echo "[3/6] 设置地址 $ADDR/24"
ip link set "$IFACE" down 2>/dev/null || true
ip addr flush dev "$IFACE" 2>/dev/null || true
ip link set "$IFACE" up
ip addr add "$ADDR/24" dev "$IFACE" 2>/dev/null || true

echo "[4/6] 启动 hostapd"
pkill -x hostapd 2>/dev/null || true
sleep 1
if ! hostapd -B "$CONF"; then
    echo "hostapd 启动失败，先按 USB 方式排查；可执行 sudo bash wifi_ap_down.sh 还原" >&2
    exit 1
fi

echo "[5/6] 重启 DHCP 服务"
systemctl restart isc-dhcp-server 2>/dev/null || systemctl start isc-dhcp-server 2>/dev/null || true

echo "[6/6] 状态"
sleep 2
iw dev "$IFACE" info 2>/dev/null | grep -E 'ssid|type|channel'
ip -br addr show "$IFACE"
echo "dhcp: $(systemctl is-active isc-dhcp-server 2>/dev/null)"
echo
echo "热点 SSID : $SSID"
echo "小车地址  : $ADDR"
echo "电脑连上后: ssh wheeltec@$ADDR"
