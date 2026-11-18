"""GUI 离屏自检：不需要真实显示服务，直接渲染主窗口并保存 PNG。

    QT_QPA_PLATFORM=offscreen python3 tests/gui_snapshot.py /tmp/gui.png

用途：
  1. 在没有图形环境（或图形环境不稳定）的机器上验证界面布局；
  2. 报告里需要的界面截图，可以先这样生成，再在真实桌面上补一张。
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PyQt5 import QtWidgets  # noqa: E402

from sniffer import decode  # noqa: E402
from sniffer.gui import MainWindow  # noqa: E402
from sniffer.pcapfile import read_pcap  # noqa: E402


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/gui.png"
    app = QtWidgets.QApplication(sys.argv[:1])

    win = MainWindow()
    win.resize(1280, 800)

    linktype, packets = read_pcap(os.path.join(ROOT, "demo", "demo.pcap"))
    parsed = [
        decode.parse(data, linktype, ts=ts, index=i + 1)
        for i, (ts, _caplen, _wirelen, data) in enumerate(packets)
    ]
    win.model.add_packets(parsed)

    # 选中一个 HTTP 包，让详情树和十六进制区有内容
    for row, pkt in enumerate(parsed):
        if pkt.app is not None and pkt.app.proto == "HTTP" and pkt.sport != 80:
            win.table.selectRow(row)
            break
    app.processEvents()

    ok = win.grab().save(out)
    print(f"saved={out} ok={ok} rows={len(parsed)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
