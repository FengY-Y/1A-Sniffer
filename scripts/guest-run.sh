#!/bin/bash
# 在客户机里由 vmrun 调起：用 sudo -S 喂密码，跑完整的 bootstrap，输出落到日志。
# 由主机通过 vmrun copyFileFromHostToGuest 复制进 /home/fy/ 后执行。
PASS="${1:-123456}"
USER_HOME="/home/fy"

rm -f "$USER_HOME/bootstrap.log"
{
  echo "=== start $(date) ==="
  echo "$PASS" | sudo -S env HOME="$USER_HOME" DEBIAN_FRONTEND=noninteractive \
      bash "$USER_HOME/vm-bootstrap.sh" 10.10.10.10
  echo "=== EXIT=$? ==="
} > "$USER_HOME/bootstrap.log" 2>&1

chown -R fy:fy "$USER_HOME/bootstrap.log" 2>/dev/null
