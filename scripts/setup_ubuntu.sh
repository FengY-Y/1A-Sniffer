#!/usr/bin/env bash
# 在 Ubuntu 虚拟机里一次性装好实验 1A 需要的依赖。
# 用法： bash scripts/setup_ubuntu.sh
set -euo pipefail

echo "==> 更新软件源"
sudo apt update

echo "==> 安装抓包与 GUI 依赖"
sudo apt install -y \
    build-essential cmake git \
    libpcap-dev tcpdump wireshark-common \
    python3 python3-pip python3-pyqt5 \
    qt6-base-dev qt6-tools-dev 2>/dev/null || \
sudo apt install -y build-essential cmake git libpcap-dev tcpdump python3 python3-pyqt5

echo "==> 检查 libpcap"
ldconfig -p | grep -i libpcap || echo "警告：没有找到 libpcap.so"

echo "==> 检查 python 包"
python3 - <<'PY'
import ctypes.util
print("find_library('pcap') =", ctypes.util.find_library("pcap"))
try:
    import PyQt5
    print("PyQt5 已安装")
except ImportError:
    print("PyQt5 未安装：sudo apt install -y python3-pyqt5")
PY

echo
echo "==> 运行方式（二选一）"
echo "  1) sudo python3 -m sniffer.cli -i eth0 -f 'tcp port 80'"
echo "  2) 给解释器加能力，之后不用 sudo："
echo "     sudo setcap cap_net_raw,cap_net_admin=eip \$(readlink -f \$(which python3))"
echo
echo "注意：setcap 之后任何 Python 脚本都能抓包，仅限实验虚拟机里这么干。"
echo "装完建议打一个快照：VBoxManage snapshot <vm> take clean"
