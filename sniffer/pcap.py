"""libpcap 的 ctypes 绑定。

只封装实验 1A 用得到的部分：枚举网卡、打开设备、BPF 过滤、读取数据包、
统计信息、写 pcap 文件。

在 Linux 上依赖 libpcap（sudo apt install libpcap-dev）。
"""
from __future__ import annotations

import ctypes
import ctypes.util
from typing import List, Optional, Tuple

PCAP_ERRBUF_SIZE = 256
PCAP_NETMASK_UNKNOWN = 0xFFFFFFFF


class PcapError(RuntimeError):
    pass


# ---------------------------------------------------------------- ctypes 结构
class Timeval(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_long), ("tv_usec", ctypes.c_long)]


class PcapPkthdr(ctypes.Structure):
    _fields_ = [
        ("ts", Timeval),
        ("caplen", ctypes.c_uint32),
        ("len", ctypes.c_uint32),
    ]


class PcapIf(ctypes.Structure):
    pass


PcapIf._fields_ = [
    ("next", ctypes.POINTER(PcapIf)),
    ("name", ctypes.c_char_p),
    ("description", ctypes.c_char_p),
    ("addresses", ctypes.c_void_p),
    ("flags", ctypes.c_uint),
]


class BpfProgram(ctypes.Structure):
    _fields_ = [("bf_len", ctypes.c_uint), ("bf_insns", ctypes.c_void_p)]


class PcapStat(ctypes.Structure):
    _fields_ = [
        ("ps_recv", ctypes.c_uint),
        ("ps_drop", ctypes.c_uint),
        ("ps_ifdrop", ctypes.c_uint),
    ]


_lib = None


def lib():
    """加载 libpcap（只加载一次）。"""
    global _lib
    if _lib is not None:
        return _lib
    candidates = [
        "pcap",
        "libpcap.so.1",
        "libpcap.so.0.9",
        "libpcap.so.0.8",
        "libpcap.so",
        "wpcap.dll",
        "libpcap.dylib",
    ]
    for name in candidates:
        try:
            found = ctypes.util.find_library(name) or name
            _lib = ctypes.CDLL(found)
            break
        except OSError:
            continue
    if _lib is None:
        raise PcapError("没有找到 libpcap，请先安装：sudo apt install -y libpcap-dev")

    L = _lib
    L.pcap_create.restype = ctypes.c_void_p
    L.pcap_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    L.pcap_activate.restype = ctypes.c_int
    L.pcap_activate.argtypes = [ctypes.c_void_p]
    L.pcap_close.argtypes = [ctypes.c_void_p]
    L.pcap_datalink.restype = ctypes.c_int
    L.pcap_datalink.argtypes = [ctypes.c_void_p]
    L.pcap_next_ex.restype = ctypes.c_int
    L.pcap_next_ex.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.POINTER(PcapPkthdr)),
        ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
    ]
    L.pcap_compile.restype = ctypes.c_int
    L.pcap_compile.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(BpfProgram),
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_uint32,
    ]
    L.pcap_setfilter.restype = ctypes.c_int
    L.pcap_setfilter.argtypes = [ctypes.c_void_p, ctypes.POINTER(BpfProgram)]
    for name, argtype in (
        ("pcap_set_snaplen", ctypes.c_int),
        ("pcap_set_promisc", ctypes.c_int),
        ("pcap_set_timeout", ctypes.c_int),
        ("pcap_set_buffer_size", ctypes.c_int),
    ):
        fn = getattr(L, name, None)
        if fn is not None:
            fn.restype = ctypes.c_int
            fn.argtypes = [ctypes.c_void_p, argtype]
    if hasattr(L, "pcap_geterr"):
        L.pcap_geterr.restype = ctypes.c_char_p
        L.pcap_geterr.argtypes = [ctypes.c_void_p]
    L.pcap_freecode.restype = None
    L.pcap_freecode.argtypes = [ctypes.POINTER(BpfProgram)]
    L.pcap_stats.restype = ctypes.c_int
    L.pcap_stats.argtypes = [ctypes.c_void_p, ctypes.POINTER(PcapStat)]
    L.pcap_findalldevs.restype = ctypes.c_int
    L.pcap_findalldevs.argtypes = [ctypes.POINTER(ctypes.POINTER(PcapIf)), ctypes.c_char_p]
    L.pcap_freealldevs.restype = None
    L.pcap_freealldevs.argtypes = [ctypes.POINTER(PcapIf)]
    L.pcap_open_offline.restype = ctypes.c_void_p
    L.pcap_open_offline.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    L.pcap_dump_open.restype = ctypes.c_void_p
    L.pcap_dump_open.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    L.pcap_dump.restype = None
    L.pcap_dump.argtypes = [ctypes.c_void_p, ctypes.POINTER(PcapPkthdr), ctypes.POINTER(ctypes.c_ubyte)]
    L.pcap_dump_close.restype = None
    L.pcap_dump_close.argtypes = [ctypes.c_void_p]
    return _lib


# ---------------------------------------------------------------- 设备列表
def list_devices() -> List[Tuple[str, str]]:
    """返回 [(设备名, 描述), ...]，给 GUI 的下拉框用。"""
    L = lib()
    errbuf = ctypes.create_string_buffer(PCAP_ERRBUF_SIZE)
    alldevs = ctypes.POINTER(PcapIf)()
    if L.pcap_findalldevs(ctypes.byref(alldevs), errbuf) != 0:
        raise PcapError(errbuf.value.decode("utf-8", "replace"))
    out = []
    dev = alldevs
    while bool(dev):
        d = dev.contents
        name = d.name.decode("utf-8", "replace") if d.name else ""
        desc = d.description.decode("utf-8", "replace") if d.description else ""
        # flags: 1 = loopback, 2 = up, 4 = running
        out.append((name, desc or ("回环接口" if d.flags & 1 else "")))
        dev = d.next
    L.pcap_freealldevs(alldevs)
    return out


class Capture:
    """一个已激活的抓包句柄。线程内使用，不要跨线程共享。"""

    def __init__(
        self,
        device: str,
        snaplen: int = 262144,
        promisc: bool = True,
        timeout_ms: int = 100,
        buffer_bytes: int = 32 * 1024 * 1024,
    ):
        L = lib()
        self._L = L
        errbuf = ctypes.create_string_buffer(PCAP_ERRBUF_SIZE)
        handle = L.pcap_create(device.encode(), errbuf)
        if not handle:
            raise PcapError(errbuf.value.decode("utf-8", "replace"))

        L.pcap_set_snaplen(handle, snaplen)
        L.pcap_set_promisc(handle, 1 if promisc else 0)
        L.pcap_set_timeout(handle, timeout_ms)
        L.pcap_set_buffer_size(handle, buffer_bytes)
        rc = L.pcap_activate(handle)
        if rc < 0:
            msg = L.pcap_geterr(handle).decode("utf-8", "replace") if hasattr(L, "pcap_geterr") \
                else f"pcap_activate 返回 {rc}"
            L.pcap_close(handle)
            raise PcapError(msg)

        self._h = handle
        self.device = device
        self.linktype = L.pcap_datalink(handle)
        self._dumper = None
        self._header = ctypes.POINTER(PcapPkthdr)()
        self._data = ctypes.POINTER(ctypes.c_ubyte)()

    # -- 抓包 ---------------------------------------------------------
    def next_packet(self) -> Optional[Tuple[float, int, int, bytes]]:
        """返回 (时间戳, caplen, wirelen, 字节) ；超时返回 None。"""
        rc = self._L.pcap_next_ex(
            self._h, ctypes.byref(self._header), ctypes.byref(self._data)
        )
        if rc == 0:          # 超时，没有包
            return None
        if rc == 1:
            h = self._header.contents
            ts = h.ts.tv_sec + h.ts.tv_usec / 1e6
            caplen = int(h.caplen)
            buf = ctypes.string_at(self._data, caplen)
            return ts, caplen, int(h.len), buf
        if rc == -2:         # 读到文件尾（离线模式）
            raise EOFError
        raise PcapError("pcap_next_ex 失败")

    # -- 过滤 ---------------------------------------------------------
    def set_filter(self, expression: str, netmask: int = PCAP_NETMASK_UNKNOWN) -> None:
        """把 BPF 表达式编译进内核，之后只有匹配的包会上来。"""
        if not expression or not expression.strip():
            expression = ""   # 空表达式 = 全收
        L = self._L
        prog = BpfProgram()
        rc = L.pcap_compile(self._h, ctypes.byref(prog), expression.encode(), 1, netmask)
        if rc != 0:
            raise PcapError(f"过滤表达式编译失败: {expression}")
        try:
            if L.pcap_setfilter(self._h, ctypes.byref(prog)) != 0:
                raise PcapError("pcap_setfilter 失败")
        finally:
            L.pcap_freecode(ctypes.byref(prog))

    # -- 统计 ---------------------------------------------------------
    def stats(self) -> Tuple[int, int]:
        """返回 (内核已交给我们的包数, 因缓冲区满丢弃的包数)。"""
        st = PcapStat()
        if self._L.pcap_stats(self._h, ctypes.byref(st)) != 0:
            return (0, 0)
        return (int(st.ps_recv), int(st.ps_drop))

    # -- 保存 ---------------------------------------------------------
    def start_dump(self, path: str) -> None:
        self._dumper = self._L.pcap_dump_open(self._h, path.encode())
        if not self._dumper:
            raise PcapError(f"无法写 pcap 文件: {path}")

    def dump(self, ts: float, caplen: int, wirelen: int, data: bytes) -> None:
        """把刚刚抓到的包原样写进 pcap 文件。"""
        if not self._dumper:
            return
        hdr = PcapPkthdr()
        hdr.ts.tv_sec = int(ts)
        hdr.ts.tv_usec = int(round((ts - int(ts)) * 1e6))
        hdr.caplen = caplen
        hdr.len = wirelen
        buf = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        self._L.pcap_dump(self._dumper, ctypes.byref(hdr), buf)

    def close(self) -> None:
        if getattr(self, "_dumper", None):
            self._L.pcap_dump_close(self._dumper)
            self._dumper = None
        if getattr(self, "_h", None):
            self._L.pcap_close(self._h)
            self._h = None


def open_offline(path: str) -> Capture:
    """打开 pcap 文件，接口与实时抓包一致（next_packet 读到末尾抛 EOFError）。"""
    L = lib()
    errbuf = ctypes.create_string_buffer(PCAP_ERRBUF_SIZE)
    h = L.pcap_open_offline(path.encode(), errbuf)
    if not h:
        raise PcapError(errbuf.value.decode("utf-8", "replace"))
    cap = Capture.__new__(Capture)
    cap._L = L
    cap._h = h
    cap.device = path
    cap.linktype = L.pcap_datalink(h)
    cap._dumper = None
    cap._header = ctypes.POINTER(PcapPkthdr)()
    cap._data = ctypes.POINTER(ctypes.c_ubyte)()
    return cap
