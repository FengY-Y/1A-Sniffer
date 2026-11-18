#!/bin/bash
# 由 vmrun 以 fy 身份调起，给克隆体设置身份：主机名、machine-id、静态 IP。
#   bash victim-setup.sh <密码> <主机名> <IP>
PASS="${1:-123456}"
NAME="${2:-victim}"
IP="${3:-10.10.10.20}"

{
  echo "=== before ==="
  hostname
  cat /etc/machine-id
  ip -4 -br addr show

  echo "=== 设置主机名与 machine-id ==="
  echo "$PASS" | sudo -S bash -c "
    hostnamectl set-hostname $NAME
    truncate -s 0 /etc/machine-id
    rm -f /var/lib/dbus/machine-id
    systemd-machine-id-setup
  "

  echo "=== 设置静态 IP ==="
  echo "$PASS" | sudo -S bash /home/fy/fix-labnet.sh "$IP"

  echo "=== after ==="
  hostname
  cat /etc/machine-id
  ip -4 -br addr show
} > /home/fy/victim-setup.log 2>&1
