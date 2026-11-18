"""PyQt5 图形界面：Wireshark 经典三栏布局。

    ┌──────────────────────── 包列表 ────────────────────────┐
    │ No.  Time  Source  Destination  Protocol  Length  Info │
    ├───────────── 协议树 ─────────────┬──── 十六进制 ────────┤
    │ ▸ Ethernet II                   │ 0000  aa bb cc ...   │
    │ ▸ IPv4                          │                      │
    │ ▸ TCP                           │                      │
    └─────────────────────────────────┴──────────────────────┘

运行：sudo python3 -m sniffer.gui
（或者给 python3 加 cap_net_raw 能力，见 docs）
"""
from __future__ import annotations

import sys
import time
from typing import List

import os
import subprocess

try:
    from PyQt5 import QtCore, QtGui, QtWidgets
except ImportError:      # pragma: no cover
    raise SystemExit("需要 PyQt5： sudo apt install -y python3-pyqt5")

from . import decode
from .engine import CaptureEngine
from .flows import ProcessResolver
from .pcap import PcapError, list_devices
from .pcapfile import write_pcap

COLUMNS = ["No.", "Time", "Source", "Destination", "Protocol", "Length", "Info"]


class PacketModel(QtCore.QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self.packets: List[decode.Packet] = []
        self.max_rows = 200000

    # -- Qt 接口 ------------------------------------------------------
    def rowCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.packets)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal:
            return COLUMNS[section]
        return None

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        pkt = self.packets[index.row()]
        if role == QtCore.Qt.DisplayRole:
            col = index.column()
            if col == 0:
                return pkt.index
            if col == 1:
                return time.strftime("%H:%M:%S", time.localtime(pkt.ts)) + \
                       f".{int((pkt.ts % 1) * 1000):03d}"
            if col == 2:
                return pkt.src
            if col == 3:
                return pkt.dst
            if col == 4:
                return pkt.app.proto if pkt.app else pkt.proto_name
            if col == 5:
                return pkt.wirelen
            return pkt.summary()
        if role == QtCore.Qt.ForegroundRole:
            proto = pkt.app.proto if pkt.app else pkt.proto_name
            color = {"TCP": "#1a5fb4", "UDP": "#26a269", "ICMP": "#c64600",
                     "ARP": "#813d9c", "HTTP": "#e5a50a", "DNS": "#63452c",
                     "TLS": "#a51d2d"}.get(proto)
            if color:
                return QtGui.QColor(color)
        if role == QtCore.Qt.TextAlignmentRole and index.column() in (0, 5):
            return int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        return None

    # -- 自己的方法 ---------------------------------------------------
    def add_packets(self, pkts: List[decode.Packet]):
        if not pkts:
            return
        start = len(self.packets)
        self.beginInsertRows(QtCore.QModelIndex(), start, start + len(pkts) - 1)
        self.packets.extend(pkts)
        self.endInsertRows()
        if len(self.packets) > self.max_rows:
            drop = len(self.packets) - self.max_rows
            self.beginRemoveRows(QtCore.QModelIndex(), 0, drop - 1)
            del self.packets[:drop]
            self.endRemoveRows()

    def clear(self):
        self.beginResetModel()
        self.packets.clear()
        self.endResetModel()


class FlowModel(QtCore.QAbstractTableModel):
    HEADER = ["Proto", "Client", "Server", "App", "Packets", "Bytes", "Duration", "State", "进程"]

    def __init__(self):
        super().__init__()
        self.rows: List[List[str]] = []

    def rowCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.HEADER)

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal:
            return self.HEADER[section]
        return None

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid() or role != QtCore.Qt.DisplayRole:
            return None
        return self.rows[index.row()][index.column()]

    def set_rows(self, rows: List[List[str]]):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("1A Sniffer - 网络嗅探器")
        # 按屏幕可用区域定尺寸和位置，避免右侧按钮、底部状态栏被裁掉
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        w = min(1180, screen.width() - 90)
        h = min(760, screen.height() - 70)
        self.resize(w, h)
        self.move(screen.x() + 10, screen.y() + 10)

        self.engine: CaptureEngine | None = None
        self.model = PacketModel()
        self.flow_model = FlowModel()
        self.resolver = ProcessResolver()
        self._pending: List[decode.Packet] = []

        self._build_ui()
        self._refresh_devices()

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._drain)
        self.timer.start(60)
        self.flow_timer = QtCore.QTimer(self)
        self.flow_timer.timeout.connect(self._refresh_flows)
        self.flow_timer.start(1000)

        # 演示/录屏用：SNIFFER_AUTOSTART=1 时自动开始抓包
        if os.environ.get("SNIFFER_AUTOSTART") == "1":
            QtCore.QTimer.singleShot(400, self._auto_start)

    def _auto_start(self) -> None:
        if self.engine is not None:
            return
        self.start_btn.setChecked(True)
        self._toggle_capture()


    # ------------------------------------------------------------------
    def _build_ui(self):
        tb = self.addToolBar("capture")
        tb.setMovable(False)

        tb.addWidget(QtWidgets.QLabel(" 网卡 "))
        self.dev_combo = QtWidgets.QComboBox()
        self.dev_combo.setMinimumWidth(260)
        tb.addWidget(self.dev_combo)

        self.refresh_btn = QtWidgets.QPushButton("刷新")
        self.refresh_btn.clicked.connect(self._refresh_devices)
        tb.addWidget(self.refresh_btn)

        tb.addSeparator()
        tb.addWidget(QtWidgets.QLabel(" 过滤 "))
        self.filter_edit = QtWidgets.QLineEdit()
        self.filter_edit.setPlaceholderText('BPF 表达式，如 tcp port 80 / icmp / host 10.0.2.15')
        self.filter_edit.setMinimumWidth(340)
        self.filter_edit.returnPressed.connect(self._restart_with_filter)
        tb.addWidget(self.filter_edit)

        self.start_btn = QtWidgets.QPushButton("开始")
        self.start_btn.setCheckable(True)
        self.start_btn.clicked.connect(self._toggle_capture)
        tb.addWidget(self.start_btn)

        self.clear_btn = QtWidgets.QPushButton("清空")
        self.clear_btn.clicked.connect(self._clear)
        tb.addWidget(self.clear_btn)

        self.save_btn = QtWidgets.QPushButton("保存 pcap")
        self.save_btn.clicked.connect(self._save_pcap)
        tb.addWidget(self.save_btn)

        self.autoscroll = QtWidgets.QCheckBox("自动滚动")
        self.autoscroll.setChecked(True)
        tb.addWidget(self.autoscroll)

        # 包列表
        self.table = QtWidgets.QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 70)
        self.table.setColumnWidth(1, 110)
        self.table.setColumnWidth(2, 170)
        self.table.setColumnWidth(3, 170)
        self.table.setColumnWidth(4, 80)
        self.table.setColumnWidth(5, 70)
        self.table.selectionModel().selectionChanged.connect(self._on_select)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["字段", "值"])
        self.tree.setColumnWidth(0, 220)
        self.tree.setAlternatingRowColors(True)

        self.hexview = QtWidgets.QPlainTextEdit()
        self.hexview.setReadOnly(True)
        self.hexview.setFont(QtGui.QFont("Monospace", 9))
        self.hexview.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)

        bottom = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        bottom.addWidget(self.tree)
        bottom.addWidget(self.hexview)
        bottom.setSizes([460, 700])

        top = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        top.addWidget(self.table)
        top.addWidget(bottom)
        top.setSizes([430, 280])

        self.flows_view = QtWidgets.QTableView()
        self.flows_view.setModel(self.flow_model)
        self.flows_view.horizontalHeader().setStretchLastSection(True)
        self.flows_view.setAlternatingRowColors(True)
        self.flows_view.verticalHeader().setVisible(False)

        tabs = QtWidgets.QTabWidget()
        tabs.addTab(top, "数据包")
        tabs.addTab(self.flows_view, "流追踪")
        self.tabs = tabs
        self.setCentralWidget(tabs)

        self.status = self.statusBar()
        self.status_label = QtWidgets.QLabel("就绪")
        self.status.addWidget(self.status_label)

    # ------------------------------------------------------------------
    @staticmethod
    def _lab_interface() -> str:
        """找出挂着 10.10.10.x 的那块网卡（实验网段），找不到返回空串。"""
        want = os.environ.get("SNIFFER_IFACE", "")
        if want:
            return want
        try:
            out = subprocess.run(["ip", "-4", "-o", "addr", "show"],
                                 capture_output=True, text=True, timeout=2).stdout
        except Exception:
            return ""
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[3].startswith("10.10.10."):
                return parts[1].split("@")[0]
        return ""

    def _refresh_devices(self):
        self.dev_combo.clear()
        try:
            for name, desc in list_devices():
                self.dev_combo.addItem(f"{name}  {desc}".strip(), name)
        except PcapError as e:
            QtWidgets.QMessageBox.warning(self, "libpcap", str(e))

        # 默认选中实验网卡，省得每次手动挑
        lab = self._lab_interface()
        if lab:
            idx = self.dev_combo.findData(lab)
            if idx >= 0:
                self.dev_combo.setCurrentIndex(idx)

    def _toggle_capture(self):
        if self.start_btn.isChecked():
            self._start()
        else:
            self._stop()

    def _start(self):
        device = self.dev_combo.currentData()
        if not device:
            QtWidgets.QMessageBox.warning(self, "提示", "先选一块网卡")
            self.start_btn.setChecked(False)
            return
        bpf = self.filter_edit.text().strip()
        self.engine = CaptureEngine(device=device, bpf=bpf)
        self.engine.start()
        self.start_btn.setText("停止")
        self.status_label.setText(f"正在抓包：{device}  过滤=[{bpf or '全部'}]")

    def _stop(self):
        if self.engine:
            self.engine.stop()
            self.engine.join(timeout=2.0)
            self.engine = None
        self.start_btn.setText("开始")
        self.status_label.setText("已停止")

    def _restart_with_filter(self):
        """改了过滤表达式：重启抓包线程让新 BPF 生效（已在列表里的包保留）。"""
        if self.engine is None:
            return
        self._stop()
        self.start_btn.setChecked(True)
        self._start()

    def _clear(self):
        self.model.clear()
        self.flow_model.set_rows([])

    def _save_pcap(self):
        if not self.model.packets:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "保存为 pcap", "capture.pcap",
                                                        "pcap 文件 (*.pcap)")
        if not path:
            return
        linktype = self.model.packets[0].linktype
        write_pcap(path, [(p.ts, p.raw) for p in self.model.packets], linktype)
        self.status_label.setText(f"已保存 {len(self.model.packets)} 个包到 {path}")

    # ------------------------------------------------------------------
    def _drain(self):
        if self.engine is None:
            return
        batch = []
        for _ in range(4000):
            try:
                batch.append(self.engine.queue.get_nowait())
            except Exception:
                break
        if batch:
            self.model.add_packets(batch)
            if self.autoscroll.isChecked():
                self.table.scrollToBottom()
        st = (f"已抓 {self.engine.total_packets} 包 / {self.engine.total_bytes} B   "
              f"内核丢包 {self.engine.kernel_dropped}   队列丢包 {self.engine.queue_dropped}   "
              f"流 {self.engine.flow_count()}")
        self.status_label.setText(st)
        if self.engine.error:
            self.status_label.setText(f"错误：{self.engine.error}")
        if self.engine.finished and self.engine is not None:
            self.start_btn.setChecked(False)
            self.start_btn.setText("开始")
            self.engine = None

    def _refresh_flows(self):
        if self.engine is None:
            return
        self.flow_model.set_rows([f.row() for f in self.engine.flow_objects()])

    def _on_select(self, *_):
        idx = self.table.currentIndex()
        if not idx.isValid() or idx.row() >= len(self.model.packets):
            return
        pkt = self.model.packets[idx.row()]
        self.tree.clear()
        for k, v in pkt.detail_rows():
            item = QtWidgets.QTreeWidgetItem([k, v])
            self.tree.addTopLevelItem(item)
        self.hexview.setPlainText(decode.hexdump(pkt.raw, limit=4096))


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
