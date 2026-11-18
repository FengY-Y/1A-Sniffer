#!/usr/bin/env bash
# 在这台虚拟机里启动 GUI 的正确方式。
#
# 背景：这台机器没有 3D 加速（VMware 在 Hyper-V 兼容模式下跑），
# Qt 默认会走 Wayland + EGL，初始化失败会把整个会话搞黑屏。
# 强制走 X11(XWayland) + 软件渲染就稳定了。
set -e
cd "$(dirname "$0")/.."

export QT_QPA_PLATFORM=xcb
export QT_XCB_GL_INTEGRATION=none
export LIBGL_ALWAYS_SOFTWARE=1
export QT_LOGGING_RULES="qt.qpa.*=false"

echo "启动 1A Sniffer（X11 + 软件渲染）..."
exec python3 -m sniffer.gui "$@"
