#!/usr/bin/env bash
# 还原：关掉热点，把 wlan0 交回 NetworkManager（可继续连路由器/热点）。
# 用法：sudo bash wifi_ap_down.sh
set -u

if [ "$(id -u)" -ne 0 ]; then
    echo "请用 sudo 运行：sudo bash $0" >&2
    exit 1
fi

echo "[1/4] 停止 hostapd"
pkill -x hostapd 2>/dev/null || true

echo "[2/4] 清掉 AP 地址"
ip addr flush dev wlan0 2>/dev/null || true

echo "[3/4] 交回 NetworkManager"
nmcli device set wlan0 managed yes 2>/dev/null || true
systemctl start wpa_supplicant 2>/dev/null || true
systemctl restart NetworkManager 2>/dev/null || true

echo "[4/4] 状态"
sleep 3
nmcli device status 2>/dev/null | head -4
echo "已还原为 NetworkManager 管理"
