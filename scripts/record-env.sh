#!/bin/bash
# 录制前把图形环境调好：不息屏、不弹通知、终端字号放大、桌面加一个准备入口。
# 只改用户级设置，不动系统配置。
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus

say() { printf "\n== %s ==\n" "$*"; }

say "关闭息屏与锁屏"
gsettings set org.gnome.desktop.session idle-delay 0
gsettings set org.gnome.desktop.screensaver lock-enabled false
gsettings set org.gnome.desktop.screensaver idle-activation-enabled false

say "关闭通知横幅（录制时不会弹出更新提示）"
gsettings set org.gnome.desktop.notifications show-banners false

say "终端字号 14、窗口 120x34"
PROFILE=$(gsettings get org.gnome.Terminal.ProfilesList default | tr -d "'")
BASE="org.gnome.Terminal.Legacy.Profile:/org/gnome/terminal/legacy/profiles:/:$PROFILE/"
gsettings set "$BASE" use-system-font false
gsettings set "$BASE" font 'Ubuntu Mono 14'
gsettings set "$BASE" default-size-columns 120
gsettings set "$BASE" default-size-rows 34

say "桌面加一个「录制准备」入口"
DESK=$(xdg-user-dir DESKTOP)
cat > "$DESK/录制准备.desktop" <<'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=录制准备
Comment=起 HTTP 服务、检查环境、打印录制流程
Exec=gnome-terminal -- bash -c "/home/fy/lab1a/scripts/record-prep.sh 180; exec bash"
Icon=media-record
Terminal=false
Categories=Utility;
EOF
chmod 755 "$DESK/录制准备.desktop"
gio set "$DESK/录制准备.desktop" metadata::trusted true 2>/dev/null

say "准备输出目录"
mkdir -p "$HOME/Videos"
ls -d "$HOME/Videos"

say "当前状态"
printf '  网卡: '; ip -4 -br addr show enp0s18 | awk '{print $3}'
printf '  8080: '; curl -s -o /dev/null -w '%{http_code}\n' http://10.10.10.10:8080/README.md || echo "不通"
printf '  单元测试: '; ( cd "$HOME/lab1a" && python3 -m unittest discover -s tests -t . >/dev/null 2>&1 ) && echo "通过" || echo "失败"
printf '  已装录屏工具: '
for t in obs ffmpeg; do command -v $t >/dev/null 2>&1 && printf '%s ' "$t"; done; echo
