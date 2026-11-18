"""流追踪：把离散的数据包聚合成「一条连接」，这是加分项，也是报告里最能写的一节。

关键点：
  * 双向流要用规范化（canonical）四元组做 key，否则 A->B 和 B->A 会分成两条；
  * 方向由第一个 SYN 决定，之后用同一 key 就直接认作同一条流；
  * 每条流只保存统计量 + 少量包序号，避免内存被大流量打爆。
"""
from __future__ import annotations

import os
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .decode import Packet

MAX_FLOWS = 20000


def canonical_key(pkt: Packet) -> Tuple:
    """(协议, IP1, 端口1, IP2, 端口2)，两个方向映射到同一个 key。"""
    a = (pkt.src, pkt.sport)
    b = (pkt.dst, pkt.dport)
    if (a[0], a[1]) <= (b[0], b[1]):
        return (pkt.proto_name, a[0], a[1], b[0], b[1])
    return (pkt.proto_name, b[0], b[1], a[0], a[1])


@dataclass
class Flow:
    key: Tuple
    proto: str
    a: Tuple[str, int]              # 客户端侧
    b: Tuple[str, int]              # 服务端侧
    first_ts: float = 0.0
    last_ts: float = 0.0
    packets: int = 0
    bytes: int = 0
    a_to_b: int = 0
    b_to_a: int = 0
    syn: bool = False
    fin: bool = False
    rst: bool = False
    app: str = ""
    host: str = ""
    process: str = ""            # 归属进程，流存活期间解析好存下来
    _proc_tried: float = 0.0
    pkt_ids: deque = field(default_factory=lambda: deque(maxlen=200))

    @property
    def duration(self) -> float:
        return max(0.0, self.last_ts - self.first_ts)

    @property
    def state(self) -> str:
        if self.rst:
            return "RST"
        if self.syn and self.fin:
            return "CLOSED"
        if self.syn:
            return "ESTAB"
        return "—"

    def add(self, pkt: Packet) -> None:
        if self.packets == 0:
            self.first_ts = pkt.ts
            # 第一个包若带 SYN，则它是客户端
            if pkt.tcp is not None and pkt.tcp.flags & 0x02 and not pkt.tcp.flags & 0x10:
                self.a, self.b = (pkt.src, pkt.sport), (pkt.dst, pkt.dport)
        self.packets += 1
        self.bytes += pkt.wirelen
        self.last_ts = pkt.ts
        if (pkt.src, pkt.sport) == self.a:
            self.a_to_b += pkt.wirelen
        else:
            self.b_to_a += pkt.wirelen
        if pkt.tcp is not None:
            f = pkt.tcp.flags
            if f & 0x02:
                self.syn = True
            if f & 0x01:
                self.fin = True
            if f & 0x04:
                self.rst = True
        if pkt.app is not None:
            if not self.app:
                self.app = pkt.app.proto
            host = pkt.app.detail.get("Host") or pkt.app.detail.get("SNI") or pkt.app.detail.get("域名")
            if host and not self.host:
                self.host = host
        if len(self.pkt_ids) < self.pkt_ids.maxlen:
            self.pkt_ids.append(pkt.index)

    def row(self) -> List[str]:
        def ep(addr: str, port: int) -> str:
            return f"[{addr}]:{port}" if ":" in addr else f"{addr}:{port}"

        return [
            self.proto,
            ep(*self.a),
            ep(*self.b),
            self.app or "",
            str(self.packets),
            str(self.bytes),
            f"{self.duration:.2f}s",
            self.state,
            self.process,
        ]


class FlowTable:
    """按最近使用排序（LRU）的流表，超过上限就淘汰最久没动的。"""

    def __init__(self, max_flows: int = MAX_FLOWS, resolver=None):
        self.max_flows = max_flows
        self.resolver = resolver      # 可选：用来在流存活期间解析归属进程
        self._flows: "OrderedDict[Tuple, Flow]" = OrderedDict()

    def __len__(self) -> int:
        return len(self._flows)

    def feed(self, pkt: Packet) -> Optional[Flow]:
        if pkt.ip is None:
            return None
        key = canonical_key(pkt)
        flow = self._flows.get(key)
        if flow is None:
            flow = Flow(key=key, proto=pkt.proto_name,
                        a=(pkt.src, pkt.sport), b=(pkt.dst, pkt.dport))
            self._flows[key] = flow
            if len(self._flows) > self.max_flows:
                self._flows.popitem(last=False)
        else:
            self._flows.move_to_end(key)
        flow.add(pkt)
        # 趁 socket 还活着把进程解析出来：连接一关，/proc/net/tcp 里就没了。
        # 只在流的前几个包上尝试；第 3 个包（握手完成）强制刷新一次快照，
        # 因为此时的 socket 才真正被 accept，缓存里的旧快照看不到它。
        if self.resolver is not None and not flow.process and flow.packets <= 10:
            flow.process = self.resolver.resolve(flow, force=(flow.packets <= 6))
        return flow

    def rows(self) -> List[List[str]]:
        return [f.row() for f in reversed(self._flows.values())]

    def flows(self) -> List[Flow]:
        return list(reversed(self._flows.values()))


# ---------------------------------------------------------------- 进程归因（加分项）
def _parse_proc_net(path: str, proto: str) -> Dict[Tuple[str, int, str, int], int]:
    """解析 /proc/net/tcp{,6}，得到 (本地, 端口, 远端, 端口) -> inode。"""
    table: Dict[Tuple[str, int, str, int], int] = {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            next(f, None)
            for line in f:
                parts = line.split()
                if len(parts) < 10:
                    continue
                laddr, raddr, inode = parts[1], parts[2], parts[9]
                try:
                    lip, lport = _split_addr(laddr, proto)
                    rip, rport = _split_addr(raddr, proto)
                    table[(lip, lport, rip, rport)] = int(inode)
                except Exception:
                    continue
    except OSError:
        pass
    return table


def _split_addr(s: str, proto: str) -> Tuple[str, int]:
    addr, port = s.split(":")
    port_i = int(port, 16)
    if proto == "tcp6":
        # /proc/net/tcp6 里是 4 个 32 位小端字
        raw = bytes.fromhex(addr)
        groups = [raw[i:i + 4][::-1].hex() for i in range(0, 16, 4)]
        return ":".join(groups), port_i
    raw = bytes.fromhex(addr)
    return ".".join(str(b) for b in raw[::-1]), port_i


def socket_owner_map() -> Dict[int, Tuple[int, str]]:
    """inode -> (pid, 进程名)。需要 root 才能看全。"""
    owners: Dict[int, Tuple[int, str]] = {}
    proc = "/proc"
    try:
        pids = [p for p in os.listdir(proc) if p.isdigit()]
    except OSError:
        return owners
    for pid in pids:
        fd_dir = os.path.join(proc, pid, "fd")
        try:
            for fd in os.listdir(fd_dir):
                try:
                    target = os.readlink(os.path.join(fd_dir, fd))
                except OSError:
                    continue
                if target.startswith("socket:["):
                    inode = int(target[8:-1])
                    try:
                        comm = open(os.path.join(proc, pid, "comm"), encoding="utf-8",
                                    errors="replace").read().strip()
                    except OSError:
                        comm = "?"
                    owners[inode] = (int(pid), comm)
        except OSError:
            continue
    return owners


class ProcessResolver:
    """把「一条流」映射到「哪个进程」，这是 p14 的进阶加分项。

    /proc 扫描是重活：要遍历所有进程的 fd，把 socket inode 和进程对上。
    所以这里做两件事：
      * 快照带 TTL（默认 3 秒），过期才重扫，避免每帧都扫一遍；
      * 只对调用方点名的那几条流做匹配，不做全量映射。

    注意：非 root 只能看到自己的进程，想要完整结果得用 sudo 跑。
    """

    def __init__(self, ttl: float = 0.5, max_scan_per_sec: int = 25):
        self.ttl = ttl
        self.max_scan_per_sec = max_scan_per_sec
        self._ts = 0.0
        self._scan_times: deque = deque()
        self._sockets: Dict[Tuple[str, int, str, int], int] = {}
        self._owners: Dict[int, Tuple[int, str]] = {}
        self._listeners: Dict[int, Tuple[str, str]] = {}

    def _ensure(self, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._ts <= self.ttl:
            return
        # 强制刷新要限速，否则高流量下会把 CPU 打满
        while self._scan_times and now - self._scan_times[0] > 1.0:
            self._scan_times.popleft()
        if force and len(self._scan_times) >= self.max_scan_per_sec:
            if now - self._ts <= self.ttl:
                return
        self._scan_times.append(now)
        self._ts = now
        sockets: Dict[Tuple[str, int, str, int], int] = {}
        for proto in ("tcp", "tcp6"):
            sockets.update(_parse_proc_net(f"/proc/net/{proto}", proto))
        self._sockets = sockets
        self._owners = socket_owner_map()
        # 监听端口 -> 进程，作为精确匹配失败时的兜底。
        # 有些内核里已 accept 的连接在 /proc/net/tcp 中 inode 为 0，
        # 但监听套接字一直有 inode，靠它反查服务端进程最稳。
        self._listeners = {}
        for (lip, lport, rip, rport), inode in sockets.items():
            if rport == 0 and inode and inode in self._owners:
                pid, comm = self._owners[inode]
                self._listeners.setdefault(lport, (lip, f"{comm}({pid})"))

    def resolve(self, flow: "Flow", force: bool = False) -> str:
        """返回 '进程名(pid)'，认不出来返回空串。

        force=True 时无视缓存重新扫一次 /proc——短连接只活几毫秒，
        必须挑准时机（握手刚完成）强制刷新，否则永远错过。
        """
        if flow.proto != "TCP":
            return ""
        self._ensure(force)
        # 1) 精确匹配：本地端点 == 流的一端，且能对上 inode
        for (lip, lport), (rip, rport) in ((flow.a, flow.b), (flow.b, flow.a)):
            inode = self._sockets.get((lip, lport, rip, rport))
            if inode and inode in self._owners:
                pid, comm = self._owners[inode]
                return f"{comm}({pid})"
        # 2) 兜底：服务端端口有监听者，就归到那个进程
        for (ip, port) in (flow.b, flow.a):
            listen = self._listeners.get(port)
            if listen and listen[0] in ("0.0.0.0", ip, "::"):
                return listen[1]
        return ""

    def resolve_many(self, flows: List["Flow"], limit: int = 50) -> List[str]:
        return [self.resolve(f) if i < limit else "" for i, f in enumerate(flows)]


_default_resolver = ProcessResolver()


def process_for_flow(flow: Flow) -> str:
    """兼容旧接口：单条流查进程。"""
    return _default_resolver.resolve(flow)
