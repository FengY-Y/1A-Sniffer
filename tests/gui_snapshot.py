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
    src = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "demo", "demo.pcap")
    app = QtWidgets.QApplication(sys.argv[:1])

    win = MainWindow()
    win.resize(1280, 800)

    linktype, packets = read_pcap(src)
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

    # 再渲染「流追踪」页：选中一条带载荷的 TCP 流，下方应显示重组内容
    from sniffer.flows import FlowTable
    table = FlowTable()
    for pkt in parsed:
        table.feed(pkt)
    flows = table.flows()
    win._flow_cache = flows
    win.flow_model.set_rows([f.row() for f in flows])
    win.tabs.setCurrentIndex(1)
    for row, f in enumerate(flows):
        if f.stream is not None:
            win.flows_view.selectRow(row)
            break
    app.processEvents()
    flows_out = out.replace(".png", "_flows.png")
    ok2 = win.grab().save(flows_out)

    print(f"saved={out} ok={ok} flows={flows_out} ok2={ok2} rows={len(parsed)}")
    return 0 if ok and ok2 else 1


if __name__ == "__main__":
    sys.exit(main())
