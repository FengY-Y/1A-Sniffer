#!/bin/bash
# 以 root 运行：把 enp0s18 收成一个干净的静态地址 10.10.10.10/24。
# 背景：Ubuntu 的 netplan 会生成 netplan-enp0s18 这个 NetworkManager 连接，
# 直接 nmcli con mod 它，重启后会被 netplan 覆盖；所以改成禁用它 + 新建独立连接。
set -x
IF=enp0s18
IP="${1:-10.10.10.10}"

# 1. 停用 netplan 生成的连接（它会做 DHCP）
nmcli connection modify netplan-$IF connection.autoconnect no 2>/dev/null || true
nmcli connection down netplan-$IF 2>/dev/null || true

# 2. 建一个专用连接
nmcli connection delete labnet 2>/dev/null || true
nmcli connection add type ethernet ifname "$IF" con-name labnet \
    ipv4.method manual ipv4.addresses "$IP/24" \
    ipv4.never-default yes ipv4.gateway "" ipv4.dns "" \
    ipv6.method disabled connection.autoconnect yes
nmcli connection up labnet

# 3. 清掉可能残留的 DHCP 地址
OLD=$(ip -4 -o addr show dev "$IF" | awk '{print $4}' | grep -v "^$IP/" | head -1)
[ -n "$OLD" ] && ip addr del "$OLD" dev "$IF"

ip -4 -br addr show "$IF"
nmcli -t -f NAME,DEVICE,STATE con show --active
