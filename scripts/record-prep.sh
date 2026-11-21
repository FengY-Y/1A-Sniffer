#!/usr/bin/env bash
# 录制前的一键准备：起 HTTP 服务、清屏、打印流程提示、可选持续造流量。
#
# 用法：
#   bash scripts/record-prep.sh            # 只准备，不造流量
#   bash scripts/record-prep.sh 120        # 准备 + 后台造 120 秒流量
set -uo pipefail

DURATION="${1:-0}"
LAB_IP="10.10.10.10"
HTTP_PORT=8080

echo "===== 录制前检查 ====="
printf ' 网卡      : '; ip -4 -br addr show enp0s18 2>/dev/null || echo "未找到 enp0s18"
printf ' 主机可达  : '; if ping -c1 -W1 10.10.10.1 >/dev/null 2>&1; then echo "通"; else echo "ICMP 无回应（Windows 防火墙默认拦截，属正常）"; fi
printf ' 单元测试  : '; (cd ~/lab1a && python3 -m unittest discover -s tests -t . >/dev/null 2>&1) && echo "24 个通过" || echo "有失败"

# HTTP 服务（被访问对象）
if ! pgrep -f "http.server $HTTP_PORT" >/dev/null 2>&1; then
    (cd ~/lab1a && nohup python3 -m http.server "$HTTP_PORT" --bind "$LAB_IP" \
        > /tmp/http.log 2>&1 &)
    sleep 1
    echo " 已启动 HTTP 服务：http://$LAB_IP:$HTTP_PORT/"
else
    echo " HTTP 服务已在运行"
fi

# 可选：后台持续造流量
if [ "$DURATION" -gt 0 ]; then
    ( bash ~/lab1a/scripts/demo_traffic.sh "$DURATION" > /tmp/traffic.log 2>&1 & )
    echo " 已开始后台造流量，持续 ${DURATION}s（日志 /tmp/traffic.log）"
fi

clear 2>/dev/null || true
cat <<EOF
┌──────────────────────────── 录制流程 ────────────────────────────┐
│ 1. 单元测试    cd ~/lab1a && python3 -m unittest discover -s tests -t . -v
│ 2. 打开界面    bash scripts/run-gui.sh
│ 3. 抓包        网卡选 enp0s18 → 点「开始」
│ 4. 造流量      另开终端：bash scripts/demo_traffic.sh 120
│ 5. 过滤        icmp → tcp port 8080 → host 10.10.10.1 and tcp port 8080
│ 6. 详情        点 HTTP 包，看协议树 + 十六进制
│ 7. 流追踪      切标签 → 选一条 8080 的流 → 下方看完整请求/响应
│ 8. 第三方      victim 开机，主机访问它，回到嗅探器看列表
└──────────────────────────────────────────────────────────────────┘

提示：
  · 终端字号调大（Ctrl+Shift++），录屏里才看得清
  · 说话前先停一秒，别抢在动作前面
  · 每段可单独重录，最后用 ffmpeg 拼接
EOF
