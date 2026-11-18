#!/usr/bin/env bash
# Ubuntu 装好后的"一条命令"配置脚本 —— 依赖、静态 IP、共享目录、免 sudo 抓包。
#
# 用法（在 sniffer 虚拟机里执行）：
#   bash vm-bootstrap.sh                 # 默认 IP 10.10.10.10
#   bash vm-bootstrap.sh 10.10.10.20     # victim 用
#
# 脚本可以重复执行，不会把已经配好的东西搞乱。
set -uo pipefail

WANT_IP="${1:-10.10.10.10}"
PREFIX=24
GATEWAY=10.10.10.1

# 用 sudo 跑时，HOME 会变成 /root，这里还原成真实用户的家目录
TARGET_HOME="$HOME"
if [ "$(id -u)" -eq 0 ] && [ -n "${SUDO_USER:-}" ]; then
    TARGET_HOME="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
fi
export DEBIAN_FRONTEND=noninteractive

say() { printf "\n\033[1;34m==> %s\033[0m\n" "$*"; }

# ---------------------------------------------------------------- 1. 依赖
say "安装实验依赖（第一次会比较久）"
sudo apt update
sudo apt install -y build-essential git cmake libpcap-dev tcpdump \
    python3 python3-pyqt5 open-vm-tools open-vm-tools-desktop || {
        echo "apt 失败：先确认 NAT 网卡能上网（ping -c1 223.5.5.5）"; exit 1; }

sudo systemctl enable --now open-vm-tools >/dev/null 2>&1 || true

# ---------------------------------------------------------------- 2. 认网卡
say "识别实验网段（VMnet1）的网卡"
DEF_IF="$(ip route show default | awk '{print $5; exit}')"
LAB_IF=""
for path in /sys/class/net/*; do
    name="$(basename "$path")"
    [ "$name" = "lo" ] && continue
    [ "$name" = "$DEF_IF" ] && continue
    LAB_IF="$name"
done

if [ -z "$LAB_IF" ]; then
    echo "只找到一块网卡（$DEF_IF），说明 VMnet1 网卡没接上。"
    echo "回 VMware：虚拟机设置 → 网络适配器 2 → 自定义 → VMnet1，再重跑本脚本。"
    exit 1
fi
echo "默认路由网卡：$DEF_IF（NAT，用于上网）"
echo "实验网段网卡：$LAB_IF（VMnet1，用于抓包）"

# ---------------------------------------------------------------- 3. 静态 IP
say "把 $LAB_IF 配成静态地址 $WANT_IP/$PREFIX"
CON="$(nmcli -t -f NAME,DEVICE connection show | awk -F: -v d="$LAB_IF" '$2==d{print $1; exit}')"
if [ -z "$CON" ]; then
    echo "没找到 $LAB_IF 对应的 NetworkManager 连接，尝试新建"
    sudo nmcli connection add type ethernet ifname "$LAB_IF" con-name labnet
    CON=labnet
fi
echo "使用连接：$CON"
sudo nmcli connection modify "$CON" \
    ipv4.method manual \
    ipv4.addresses "$WANT_IP/$PREFIX" \
    ipv4.gateway "" \
    ipv4.dns "" \
    connection.autoconnect yes
sudo nmcli connection up "$CON" >/dev/null

ip -4 -br addr show "$LAB_IF"

# ---------------------------------------------------------------- 4. 共享目录
say "挂载 VMware 共享目录（/mnt/hgfs/lab1a）"
sudo mkdir -p /mnt/hgfs
sudo vmhgfs-fuse .host:/ /mnt/hgfs -o subtype=vmhgfs-fuse,allow_other 2>/dev/null \
    || echo "共享目录没挂上（装了 open-vm-tools 后需要重新登录一次再试）"

if [ -d /mnt/hgfs/lab1a ] && [ ! -d "$TARGET_HOME/lab1a" ]; then
    cp -r /mnt/hgfs/lab1a "$TARGET_HOME/lab1a"
    [ -n "${SUDO_USER:-}" ] && chown -R "$SUDO_USER":"$SUDO_USER" "$TARGET_HOME/lab1a"
    echo "已把实验代码复制到 $TARGET_HOME/lab1a"
fi

# ---------------------------------------------------------------- 5. 免 sudo 抓包
say "给 python3 授予抓包能力（之后 GUI 不用 sudo 启动）"
PY="$(readlink -f "$(command -v python3)")"
sudo setcap cap_net_raw,cap_net_admin=eip "$PY" && echo "已设置：$PY"

# ---------------------------------------------------------------- 6. 自检
say "自检"
echo "--- 网络 ---"
ping -c 2 -W 2 "$GATEWAY" >/dev/null 2>&1 \
    && echo "到主机 $GATEWAY：通" || echo "到主机 $GATEWAY：不通（检查 VMnet1 是否选对）"
ping -c 2 -W 2 223.5.5.5 >/dev/null 2>&1 \
    && echo "外网：通" || echo "外网：不通（NAT 网卡可能没接）"

if [ -d "$TARGET_HOME/lab1a" ]; then
    echo "--- 单元测试 ---"
    ( cd "$TARGET_HOME/lab1a" && python3 -m unittest discover -s tests -t . 2>&1 | tail -3 )
    echo "--- 离线解析 demo.pcap ---"
    ( cd "$TARGET_HOME/lab1a" && python3 -m sniffer.cli -r demo/demo.pcap 2>&1 | tail -4 )
fi

cat <<EOF

完成。本机地址：$WANT_IP
下一步：
  1) 打开终端跑 GUI：   cd ~/lab1a && python3 -m sniffer.gui
  2) 命令行抓包：       cd ~/lab1a && sudo python3 -m sniffer.cli -i $LAB_IF
  3) 造流量：           bash ~/lab1a/scripts/demo_traffic.sh
  4) 打快照：           VMware 菜单「虚拟机 → 快照 → 拍摄快照」，命名 02-deps
EOF
