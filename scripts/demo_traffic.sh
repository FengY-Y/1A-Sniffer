#!/usr/bin/env bash
# 在虚拟机里制造"可被嗅探"的流量，方便截图和录屏。
#
# 用法：
#   bash scripts/demo_traffic.sh            # 默认生成一轮
#   bash scripts/demo_traffic.sh 30         # 持续 30 秒，反复发
#
# 建议同时开一个终端跑： sudo python3 -m sniffer.cli -i eth0
set -uo pipefail

DURATION="${1:-12}"
# 默认只打实验网段（10.10.10.0/24），这样 enp0s18 上才看得到
GW="${GW:-10.10.10.1}"                 # 主机（VMnet1 适配器）
TARGET="${TARGET:-10.10.10.10}"        # 对端：sniffer 本机或 victim
HTTP_PORT="${HTTP_PORT:-8080}"
URL="${URL:-http://$TARGET:$HTTP_PORT/}"

echo "网关=$GW  对端=$TARGET  HTTP=$URL  时长=${DURATION}s"

end=$((SECONDS + DURATION))
i=0
while [ $SECONDS -lt $end ]; do
    i=$((i + 1))
    echo "--- 第 $i 轮 ---"
    ping -c 2 -W 1 "$GW"     >/dev/null 2>&1 || true      # ICMP
    ping -c 2 -W 1 "$TARGET" >/dev/null 2>&1 || true
    getent hosts example.com >/dev/null 2>&1 || true      # DNS
    curl -s -m 3 -o /dev/null "$URL" || true              # HTTP
    curl -sk -m 3 -o /dev/null "https://example.com/" || true  # TLS(SNI)
    nc -z -w1 "$TARGET" 22 2>/dev/null || true            # TCP 探测
    sleep 1
done

echo "完成。用 Ctrl-C 停掉嗅探器，检查是否抓到 ARP/DNS/TCP/HTTP/TLS/ICMP。"
