"""TCP 流重组：把一段段报文拼回应用层的字节流。

为什么需要它：
    TCP 提供的是「可靠字节流」，不是「消息流」。应用写一次 send()，
    内核可能拆成好几个报文段发出去；抓包程序看到的是碎片，单包解析
    只能得到半句话。重组之后才能看到完整的 HTTP 请求/响应。

实现要点：
    * 每条流两个方向各一个缓冲区（client→server、server→client）；
    * 用 32 位序号定位写入位置，比较时按模 2^32 取有符号偏移，处理回绕；
    * 重传会带来重复数据，用「块合并 + 后到不覆盖已交付部分」去重；
    * 允许空洞（丢包/中途抓包），read() 只返回从起点连续的那一段。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .decode import hexdump

SEQ_MOD = 1 << 32
HALF = SEQ_MOD >> 1


def seq_delta(seq: int, base: int) -> int:
    """seq 相对 base 的有符号偏移，处理 32 位序号回绕。"""
    d = (seq - base) % SEQ_MOD
    return d - SEQ_MOD if d >= HALF else d


class StreamBuffer:
    """单个方向的重组缓冲区。"""

    def __init__(self, max_bytes: int = 512 * 1024):
        self.max_bytes = max_bytes
        self.base: Optional[int] = None       # 起始序号
        self.blocks: Dict[int, bytes] = {}    # 偏移 -> 数据块
        self.bytes_in = 0                     # 收到多少字节（含重复）
        self.truncated = False                # 超过上限被截断
        self.had_gap = False                  # 是否存在空洞

    # ------------------------------------------------------------------
    def feed(self, seq: int, data: bytes) -> None:
        if not data:
            return
        if self.base is None:
            self.base = seq
        off = seq_delta(seq, self.base)
        if off < 0:
            # 新数据比已知起点更早：把起点前移，已有块整体后移，避免丢开头
            shift = -off
            self.base = seq
            self.blocks = {k + shift: v for k, v in self.blocks.items()}
            off = 0
        if off >= self.max_bytes:
            self.truncated = True
            return
        end = off + len(data)
        if end > self.max_bytes:
            data = data[: self.max_bytes - off]
            end = self.max_bytes
            self.truncated = True

        self.bytes_in += len(data)
        self.blocks[off] = data
        self._merge()

    def _merge(self) -> None:
        """把重叠/相邻的块合并，避免块数随包数无限增长。"""
        if len(self.blocks) < 2:
            return
        items = sorted(self.blocks.items())
        merged: Dict[int, bytes] = {}
        cur_off, cur = items[0]
        for off, data in items[1:]:
            if off <= cur_off + len(cur):
                if off + len(data) > cur_off + len(cur):
                    cur = cur + data[cur_off + len(cur) - off:]
            else:
                merged[cur_off] = cur
                cur_off, cur = off, data
        merged[cur_off] = cur
        self.blocks = merged

    # ------------------------------------------------------------------
    def read(self, limit: int = 64 * 1024) -> Tuple[bytes, bool]:
        """返回 (从起点开始的连续字节, 是否还有洞/未到齐)。

        只有从流起点连续的数据才交出去——中间缺一段就停在那里，
        否则拼出来的文本会张冠李戴。
        """
        if not self.blocks:
            return b"", False
        items = sorted(self.blocks.items())
        out: List[bytes] = []
        pos = 0
        for off, data in items:
            if off > pos:
                break                      # 出现空洞，停止
            if off + len(data) > pos:
                out.append(data[pos - off:])
                pos = off + len(data)
        tail = max(off + len(data) for off, data in self.blocks.items())
        gap = pos < tail
        if gap:
            self.had_gap = True
        return b"".join(out)[:limit], gap


def decode_stream(data: bytes) -> str:
    """能被当成文本就按文本显示，否则退回十六进制。"""
    sample = data[:4096]
    if not sample:
        return ""
    printable = sum(1 for b in sample if 32 <= b < 127 or b in (9, 10, 13))
    if printable / len(sample) >= 0.85:
        text = data.decode("utf-8", errors="replace")
        # 统一换行符，终端和文本框里都不会出现多余的空白行
        return text.replace("\r\n", "\n").replace("\r", "\n")
    return hexdump(data, limit=4096)


class TcpStream:
    """一条 TCP 连接的双向重组结果。"""

    def __init__(self, max_bytes: int = 512 * 1024):
        self.up = StreamBuffer(max_bytes)      # 客户端 -> 服务端
        self.down = StreamBuffer(max_bytes)    # 服务端 -> 客户端

    def feed(self, from_client: bool, seq: int, payload: bytes) -> None:
        (self.up if from_client else self.down).feed(seq, payload)

    @property
    def has_data(self) -> bool:
        return bool(self.up.blocks or self.down.blocks)

    def render(self, limit: int = 64 * 1024) -> str:
        """渲染成 Wireshark「Follow TCP Stream」那种文本。"""
        parts: List[str] = []
        for arrow, label, buf in ((">>>", "客户端 → 服务端", self.up),
                                  ("<<<", "服务端 → 客户端", self.down)):
            data, gap = buf.read(limit)
            if not data:
                if buf.blocks:
                    parts.append(f"{arrow} {label}：有数据但开头缺失，无法显示")
                continue
            note = "，中间有缺失" if gap else ""
            if buf.truncated:
                note += "，已截断"
            parts.append(f"{arrow} {label}（{len(data)} 字节{note}）")
            parts.append(decode_stream(data))
            parts.append("")
        return "\n".join(parts).rstrip() or "（没有可显示的应用层载荷）"
