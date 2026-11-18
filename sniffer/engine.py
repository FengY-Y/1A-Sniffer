"""抓包引擎：一个后台线程负责 pcap_next_ex，解包后塞进队列，界面侧只管取。

为什么要单独开线程？
  pcap_next_ex 默认是阻塞的（超时 100ms 一次），如果放在 GUI 主线程里，
  界面就会卡住。所以：抓包线程 -> Queue -> 界面定时器，是这类程序的标准结构。
"""
from __future__ import annotations

import queue
import threading
from typing import List, Optional

from . import decode
from .flows import FlowTable, ProcessResolver
from .pcap import Capture, PcapError, open_offline


class _PyPcapSource:
    """没有 libpcap 时的离线兜底：用纯 Python 读 pcap（只支持读文件）。"""

    def __init__(self, path: str):
        from .pcapfile import read_pcap
        self.linktype, self._packets = read_pcap(path)
        self._i = 0

    def next_packet(self):
        if self._i >= len(self._packets):
            raise EOFError
        ts, caplen, wirelen, data = self._packets[self._i]
        self._i += 1
        return ts, caplen, wirelen, data

    def stats(self):
        return (len(self._packets), 0)

    def set_filter(self, expression: str):
        raise PcapError("纯 Python 离线模式不支持 BPF，请安装 libpcap 后重试")

    def start_dump(self, path: str):
        raise PcapError("离线模式无需再写 pcap")

    def dump(self, *args):
        pass

    def close(self):
        pass


class CaptureEngine(threading.Thread):
    def __init__(
        self,
        device: Optional[str] = None,
        path: Optional[str] = None,
        bpf: str = "",
        promisc: bool = True,
        snaplen: int = 262144,
        write_path: Optional[str] = None,
        queue_max: int = 50000,
    ):
        super().__init__(daemon=True, name="capture")
        self.device = device
        self.path = path
        self.bpf = bpf
        self.promisc = promisc
        self.snaplen = snaplen
        self.write_path = write_path
        self.queue: "queue.Queue[decode.Packet]" = queue.Queue(maxsize=queue_max)

        self.flows = FlowTable(resolver=ProcessResolver())
        self._flow_lock = threading.Lock()
        self._stop_evt = threading.Event()

        self.total_packets = 0
        self.total_bytes = 0
        self.kernel_dropped = 0
        self.queue_dropped = 0
        self.error: Optional[str] = None
        self.finished = False
        self.linktype = 0

    # ------------------------------------------------------------------
    def stop(self) -> None:
        self._stop_evt.set()

    def flow_rows(self) -> List[List[str]]:
        with self._flow_lock:
            return self.flows.rows()

    def flow_objects(self):
        """返回 Flow 对象列表（GUI 要拿到对象才能查进程）。"""
        with self._flow_lock:
            return self.flows.flows()

    def flow_count(self) -> int:
        with self._flow_lock:
            return len(self.flows)

    # ------------------------------------------------------------------
    def run(self) -> None:
        cap = None
        try:
            if self.path:
                try:
                    cap = open_offline(self.path)
                except PcapError:
                    cap = _PyPcapSource(self.path)
            else:
                cap = Capture(self.device or "any", snaplen=self.snaplen,
                              promisc=self.promisc, timeout_ms=100)
            self.linktype = cap.linktype
            if self.bpf:
                cap.set_filter(self.bpf)
            if self.write_path:
                cap.start_dump(self.write_path)

            index = 0
            while not self._stop_evt.is_set():
                try:
                    rec = cap.next_packet()
                except EOFError:
                    break
                if rec is None:
                    continue
                ts, caplen, wirelen, data = rec
                index += 1
                pkt = decode.parse(data, cap.linktype, ts, index)
                pkt.caplen = caplen
                pkt.wirelen = wirelen

                self.total_packets += 1
                self.total_bytes += wirelen
                with self._flow_lock:
                    self.flows.feed(pkt)
                if self.write_path:
                    cap.dump(ts, caplen, wirelen, data)
                try:
                    self.queue.put_nowait(pkt)
                except queue.Full:
                    self.queue_dropped += 1

            if cap is not None:
                rec, drop = cap.stats()
                self.kernel_dropped = drop
        except PcapError as e:
            self.error = str(e)
        except Exception as e:                     # 兜底，别让线程静默死掉
            self.error = f"{type(e).__name__}: {e}"
        finally:
            if cap is not None:
                cap.close()
            self.finished = True
