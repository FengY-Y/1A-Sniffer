"""纯 Python 的 pcap 文件读写。

用途有两个：
  1. 没有 root、没有 libpcap 时也能读已有的 pcap 文件（离线分析）；
  2. 单元测试里造一个 pcap，用来验证解析器。
"""
from __future__ import annotations

import struct
from typing import Iterable, Iterator, List, Tuple

MAGIC_LE = 0xA1B2C3D4       # 微秒精度，小端
MAGIC_BE = 0xD4C3B2A1
MAGIC_NS_LE = 0xA1B23C4D    # 纳秒精度


def read_pcap(path: str) -> Tuple[int, List[Tuple[float, int, int, bytes]]]:
    """返回 (linktype, [(时间戳, caplen, wirelen, 字节), ...])。"""
    with open(path, "rb") as f:
        head = f.read(24)
        if len(head) < 24:
            raise ValueError("不是合法的 pcap 文件")
        magic = struct.unpack("<I", head[:4])[0]
        if magic == MAGIC_LE:
            endian, nano = "<", False
        elif magic == MAGIC_NS_LE:
            endian, nano = "<", True
        elif struct.unpack(">I", head[:4])[0] == MAGIC_LE:
            endian, nano = ">", False
        else:
            raise ValueError(f"不支持的 pcap magic: {magic:#x}")
        linktype = struct.unpack(endian + "I", head[20:24])[0]
        out = []
        while True:
            rec = f.read(16)
            if len(rec) < 16:
                break
            sec, usec, caplen, wirelen = struct.unpack(endian + "IIII", rec)
            data = f.read(caplen)
            if len(data) < caplen:
                break
            frac = usec / 1e9 if nano else usec / 1e6
            out.append((sec + frac, caplen, wirelen, data))
    return linktype, out


def write_pcap(path: str, packets: Iterable[Tuple[float, bytes]], linktype: int = 1) -> None:
    """写一个 pcap 文件，packets 里是 (时间戳, 字节)。"""
    with open(path, "wb") as f:
        f.write(struct.pack("<IHHiIII", MAGIC_LE, 2, 4, 0, 0, 65535, linktype))
        for ts, data in packets:
            sec = int(ts)
            usec = int(round((ts - sec) * 1e6))
            f.write(struct.pack("<IIII", sec, usec, len(data), len(data)))
            f.write(data)


def iter_pcap(path: str) -> Iterator[Tuple[float, int, int, bytes, int]]:
    linktype, packets = read_pcap(path)
    for ts, caplen, wirelen, data in packets:
        yield ts, caplen, wirelen, data, linktype
