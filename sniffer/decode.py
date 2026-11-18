"""协议解析：以太网 / VLAN / IPv4 / IPv6 / TCP / UDP / ICMP / ARP，以及应用层初判。

设计原则：任何字段越界都不要抛异常，返回 None 并把已经解析出来的层保留下来。
抓包程序最忌讳因为一个畸形包把整个线程搞崩。
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------- 常量
ETH_IPV4 = 0x0800
ETH_ARP = 0x0806
ETH_IPV6 = 0x86DD
ETH_VLAN = 0x8100
ETH_QINQ = 0x88A8

LINKTYPE_NULL = 0
LINKTYPE_EN10MB = 1
LINKTYPE_RAW = 12
LINKTYPE_LINUX_SLL = 113
LINKTYPE_LINUX_SLL2 = 276

IPPROTO_ICMP = 1
IPPROTO_TCP = 6
IPPROTO_UDP = 17
IPPROTO_ICMPV6 = 58

TCP_FIN, TCP_SYN, TCP_RST, TCP_PSH, TCP_ACK, TCP_URG = 0x01, 0x02, 0x04, 0x08, 0x10, 0x20


def mac(raw: bytes) -> str:
    return ":".join(f"{b:02x}" for b in raw)


def ipv4(raw: bytes) -> str:
    return ".".join(str(b) for b in raw)


def ipv6(raw: bytes) -> str:
    """按 RFC 5952 做简化压缩：去掉每组前导 0，并把最长的连续 0 组换成 ::。"""
    groups = [f"{raw[i] << 8 | raw[i + 1]:x}" for i in range(0, 16, 2)]
    best_start, best_len, cur_start, cur_len = -1, 0, -1, 0
    for i, g in enumerate(groups + ["x"]):
        if g == "0":
            if cur_start < 0:
                cur_start, cur_len = i, 0
            cur_len += 1
        else:
            if cur_start >= 0 and cur_len > best_len:
                best_start, best_len = cur_start, cur_len
            cur_start, cur_len = -1, 0
    if best_len < 2:
        return ":".join(groups)
    head = ":".join(groups[:best_start])
    tail = ":".join(groups[best_start + best_len:])
    return f"{head}::{tail}" if head and tail else (f"{head}::" if head else f"::{tail}")


@dataclass
class Eth:
    dst: str
    src: str
    type: int
    vlans: List[int] = field(default_factory=list)


@dataclass
class IP:
    version: int
    src: str
    dst: str
    proto: int
    ttl: int
    total_len: int
    frag: bool = False
    hdr_len: int = 20


@dataclass
class TCP:
    sport: int
    dport: int
    seq: int
    ack: int
    flags: int
    window: int
    payload: bytes
    hdr_len: int

    @property
    def flag_str(self) -> str:
        names = []
        for bit, name in ((TCP_SYN, "SYN"), (TCP_ACK, "ACK"), (TCP_FIN, "FIN"),
                          (TCP_RST, "RST"), (TCP_PSH, "PSH"), (TCP_URG, "URG")):
            if self.flags & bit:
                names.append(name)
        return ",".join(names)


@dataclass
class UDP:
    sport: int
    dport: int
    length: int
    payload: bytes


@dataclass
class ICMP:
    type: int
    code: int
    payload: bytes


@dataclass
class ARP:
    op: int
    sender_mac: str
    sender_ip: str
    target_mac: str
    target_ip: str


@dataclass
class App:
    proto: str            # HTTP / DNS / TLS / DHCP / NTP / SSH ...
    info: str            # 一行摘要
    detail: Dict[str, str] = field(default_factory=dict)


@dataclass
class Packet:
    index: int
    ts: float
    caplen: int
    wirelen: int
    raw: bytes
    linktype: int
    eth: Optional[Eth] = None
    ip: Optional[IP] = None
    tcp: Optional[TCP] = None
    udp: Optional[UDP] = None
    icmp: Optional[ICMP] = None
    arp: Optional[ARP] = None
    app: Optional[App] = None
    truncated: bool = False

    # ---- 给表格/流追踪用的快捷属性
    @property
    def proto_name(self) -> str:
        if self.arp is not None:
            return "ARP"
        if self.ip is None:
            return "ETH"
        return {IPPROTO_TCP: "TCP", IPPROTO_UDP: "UDP",
                IPPROTO_ICMP: "ICMP", IPPROTO_ICMPV6: "ICMPv6"}.get(self.ip.proto, str(self.ip.proto))

    @property
    def src(self) -> str:
        if self.ip:
            return self.ip.src
        if self.arp:
            return self.arp.sender_ip
        return self.eth.src if self.eth else ""

    @property
    def dst(self) -> str:
        if self.ip:
            return self.ip.dst
        if self.arp:
            return self.arp.target_ip
        return self.eth.dst if self.eth else ""

    @property
    def sport(self) -> int:
        if self.tcp:
            return self.tcp.sport
        if self.udp:
            return self.udp.sport
        return 0

    @property
    def dport(self) -> int:
        if self.tcp:
            return self.tcp.dport
        if self.udp:
            return self.udp.dport
        return 0

    @property
    def payload(self) -> bytes:
        if self.tcp:
            return self.tcp.payload
        if self.udp:
            return self.udp.payload
        return b""

    def summary(self) -> str:
        """一行摘要，直接显示在抓包列表里。"""
        if self.app:
            base = self.app.info
        elif self.arp:
            base = f"ARP {'request' if self.arp.op == 1 else 'reply'}"
        elif self.icmp:
            base = f"ICMP type={self.icmp.type} code={self.icmp.code}"
        elif self.tcp:
            base = f"[{self.tcp.flag_str}]"
        else:
            base = ""
        if self.ip:
            if self.sport:
                s = f"[{self.src}]:{self.sport}" if ":" in self.src else f"{self.src}:{self.sport}"
                d = f"[{self.dst}]:{self.dport}" if ":" in self.dst else f"{self.dst}:{self.dport}"
                head = f"{s} -> {d}"
            else:
                head = f"{self.src} -> {self.dst}"
            return f"{head}  {base} len={self.wirelen}"
        return f"{self.src} -> {self.dst}  {base}"

    def detail_rows(self) -> List[Tuple[str, str]]:
        """详情面板用的 (字段, 值) 列表。"""
        rows: List[Tuple[str, str]] = []

        def add(layer: str, items: List[Tuple[str, str]]):
            if items:
                rows.append((f"▸ {layer}", ""))
                rows.extend(items)

        if self.eth:
            add("Ethernet II", [("目的 MAC", self.eth.dst), ("源 MAC", self.eth.src),
                                ("类型", f"0x{self.eth.type:04x}")])
            for i, v in enumerate(self.eth.vlans):
                rows.append((f"VLAN[{i}]", str(v)))
        if self.ip:
            if self.ip.version == 4:
                add("IPv4", [("源地址", self.ip.src), ("目的地址", self.ip.dst),
                             ("协议", str(self.ip.proto)), ("TTL", str(self.ip.ttl)),
                             ("总长度", str(self.ip.total_len)),
                             ("分片", "是" if self.ip.frag else "否")])
            else:
                add("IPv6", [("源地址", self.ip.src), ("目的地址", self.ip.dst),
                             ("下一头部", str(self.ip.proto)), ("跳数限制", str(self.ip.ttl)),
                             ("载荷长度", str(self.ip.total_len))])
        if self.tcp:
            add("TCP", [("源端口", str(self.tcp.sport)), ("目的端口", str(self.tcp.dport)),
                        ("序号", str(self.tcp.seq)), ("确认号", str(self.tcp.ack)),
                        ("标志", self.tcp.flag_str), ("窗口", str(self.tcp.window)),
                        ("载荷长度", str(len(self.tcp.payload)))])
        if self.udp:
            add("UDP", [("源端口", str(self.udp.sport)), ("目的端口", str(self.udp.dport)),
                        ("长度", str(self.udp.length))])
        if self.icmp:
            add("ICMP", [("类型", str(self.icmp.type)), ("代码", str(self.icmp.code))])
        if self.arp:
            add("ARP", [("操作", "请求" if self.arp.op == 1 else "应答"),
                        ("发送方 MAC", self.arp.sender_mac), ("发送方 IP", self.arp.sender_ip),
                        ("目标 MAC", self.arp.target_mac), ("目标 IP", self.arp.target_ip)])
        if self.app:
            add(f"应用层 ({self.app.proto})", list(self.app.detail.items()) or [("摘要", self.app.info)])
        return rows


# ---------------------------------------------------------------- 解析主体
def _link_offset(data: bytes, linktype: int):
    """返回 (以太网头信息, L3 起始偏移, 以太类型)。"""
    if linktype == LINKTYPE_EN10MB:
        if len(data) < 14:
            return None, 0, 0
        dst, src, etype = mac(data[0:6]), mac(data[6:12]), struct.unpack("!H", data[12:14])[0]
        off = 14
        vlans = []
        while etype in (ETH_VLAN, ETH_QINQ) and len(data) >= off + 4:
            tci, etype = struct.unpack("!HH", data[off:off + 4])
            vlans.append(tci & 0x0FFF)
            off += 4
        return Eth(dst, src, etype, vlans), off, etype
    if linktype == LINKTYPE_LINUX_SLL:
        if len(data) < 16:
            return None, 0, 0
        etype = struct.unpack("!H", data[14:16])[0]
        return None, 16, etype
    if linktype == LINKTYPE_LINUX_SLL2:
        if len(data) < 20:
            return None, 0, 0
        etype = struct.unpack("!H", data[0:2])[0]
        return None, 20, etype
    if linktype == LINKTYPE_NULL:
        return None, 4, ETH_IPV4
    if linktype == LINKTYPE_RAW:
        return None, 0, 0
    return None, 14, 0


def _parse_ipv4(data: bytes, off: int) -> Tuple[Optional[IP], int]:
    if len(data) < off + 20:
        return None, off
    vihl = data[off]
    hdr_len = (vihl & 0x0F) * 4
    total_len = struct.unpack("!H", data[off + 2:off + 4])[0]
    frag_field = struct.unpack("!H", data[off + 6:off + 8])[0]
    ttl, proto = data[off + 8], data[off + 9]
    src, dst = ipv4(data[off + 12:off + 16]), ipv4(data[off + 16:off + 20])
    frag = bool(frag_field & 0x3FFF)  # MF 或 片偏移非 0
    ip = IP(4, src, dst, proto, ttl, total_len, frag, hdr_len)
    return ip, off + hdr_len


def _parse_ipv6(data: bytes, off: int) -> Tuple[Optional[IP], int]:
    if len(data) < off + 40:
        return None, off
    payload_len = struct.unpack("!H", data[off + 4:off + 6])[0]
    nxt, hop = data[off + 6], data[off + 7]
    src, dst = ipv6(data[off + 8:off + 24]), ipv6(data[off + 24:off + 40])
    cur = off + 40
    proto = nxt
    # 跳过扩展头：逐跳(0)/路由(43)/目的选项(60)/AH(51)/分片(44)
    for _ in range(8):
        if proto in (0, 43, 60):
            if len(data) < cur + 2:
                break
            proto, hdr_ext = data[cur], data[cur + 1]
            cur += (hdr_ext + 1) * 8
        elif proto == 51:
            if len(data) < cur + 2:
                break
            proto = data[cur]
            cur += (data[cur + 1] + 2) * 4
        elif proto == 44:
            if len(data) < cur + 8:
                break
            proto = data[cur]
            cur += 8
        else:
            break
    ip = IP(6, src, dst, proto, hop, payload_len, False, cur - off)
    return ip, cur


def _parse_tcp(data: bytes, off: int) -> Optional[TCP]:
    if len(data) < off + 20:
        return None
    sport, dport, seq, ack = struct.unpack("!HHII", data[off:off + 12])
    hdr_len = (data[off + 12] >> 4) * 4
    flags = data[off + 13]
    window = struct.unpack("!H", data[off + 14:off + 16])[0]
    payload = data[off + hdr_len:] if hdr_len >= 20 else b""
    return TCP(sport, dport, seq, ack, flags, window, payload, hdr_len)


def _parse_udp(data: bytes, off: int) -> Optional[UDP]:
    if len(data) < off + 8:
        return None
    sport, dport, length = struct.unpack("!HHH", data[off:off + 6])
    return UDP(sport, dport, length, data[off + 8:])


def _parse_icmp(data: bytes, off: int) -> Optional[ICMP]:
    if len(data) < off + 4:
        return None
    return ICMP(data[off], data[off + 1], data[off + 4:])


def _parse_arp(data: bytes, off: int) -> Optional[ARP]:
    if len(data) < off + 28:
        return None
    op = struct.unpack("!H", data[off + 6:off + 8])[0]
    return ARP(op, mac(data[off + 8:off + 14]), ipv4(data[off + 14:off + 18]),
               mac(data[off + 18:off + 24]), ipv4(data[off + 24:off + 28]))


# ---------------------------------------------------------------- 应用层
HTTP_METHODS = (b"GET ", b"POST ", b"HEAD ", b"PUT ", b"DELETE ", b"OPTIONS ",
                b"CONNECT ", b"PATCH ", b"TRACE ")


def _http(payload: bytes) -> Optional[App]:
    head = payload.split(b"\r\n\r\n", 1)[0]
    lines = head.split(b"\r\n")
    if not lines:
        return None
    first = lines[0]
    detail: Dict[str, str] = {}
    if first.startswith(b"HTTP/"):
        detail["类型"] = "响应"
        detail["状态"] = first[9:].decode("latin-1", "replace") if len(first) > 9 else ""
    elif first.startswith(HTTP_METHODS):
        parts = first.split(b" ", 2)
        detail["类型"] = "请求"
        detail["方法"] = parts[0].decode("latin-1", "replace")
        detail["URI"] = parts[1].decode("latin-1", "replace") if len(parts) > 1 else ""
    else:
        return None
    for line in lines[1:]:
        if b":" not in line:
            continue
        k, v = line.split(b":", 1)
        key = k.decode("latin-1", "replace").strip()
        if key.lower() in ("host", "user-agent", "content-type", "content-length", "referer", "cookie"):
            detail[key] = v.decode("latin-1", "replace").strip()[:120]
    info = " ".join(f"{k}={v}" for k, v in detail.items() if k in ("方法", "URI", "状态", "Host"))
    return App("HTTP", info or "HTTP", detail)


def _dns_name(payload: bytes) -> Optional[str]:
    if len(payload) < 13:
        return None
    qdcount = struct.unpack("!H", payload[4:6])[0]
    if qdcount < 1:
        return None
    labels, i, guard = [], 12, 0
    while i < len(payload) and guard < 64:
        ln = payload[i]
        guard += 1
        if ln == 0:
            break
        if ln & 0xC0:      # 压缩指针，查询里一般不会出现
            break
        i += 1
        labels.append(payload[i:i + ln].decode("latin-1", "replace"))
        i += ln
    return ".".join(labels) if labels else None


def _dns(payload: bytes) -> Optional[App]:
    name = _dns_name(payload)
    if not name:
        return None
    qd = struct.unpack("!H", payload[4:6])[0]
    an = struct.unpack("!H", payload[6:8])[0]
    kind = "查询" if an == 0 else "应答"
    return App("DNS", f"{kind} {name}", {"域名": name, "问题数": str(qd), "回答数": str(an)})


def _tls_sni(payload: bytes) -> Optional[str]:
    """从 ClientHello 里取 SNI——HTTPS 抓不到内容，但域名是明文的。"""
    try:
        if len(payload) < 5 or payload[0] != 0x16:
            return None
        p = 5
        if payload[p] != 0x01:       # ClientHello
            return None
        p += 4                       # 跳过 type(1) + 长度(3)
        p += 2                       # client_version
        p += 32                      # random
        sid_len = payload[p]
        p += 1 + sid_len
        cs_len = struct.unpack("!H", payload[p:p + 2])[0]
        p += 2 + cs_len
        comp_len = payload[p]
        p += 1 + comp_len
        ext_total = struct.unpack("!H", payload[p:p + 2])[0]
        p += 2
        end = p + ext_total
        while p + 4 <= end:
            etype, elen = struct.unpack("!HH", payload[p:p + 4])
            p += 4
            if etype == 0x0000:      # server_name
                q = p + 2
                while q + 3 <= p + elen:
                    ntype, nlen = payload[q], struct.unpack("!H", payload[q + 1:q + 3])[0]
                    if ntype == 0:
                        return payload[q + 3:q + 3 + nlen].decode("latin-1", "replace")
                    q += 3 + nlen
            p += elen
    except Exception:
        return None
    return None


def _app(pkt: Packet) -> Optional[App]:
    payload = pkt.payload
    if pkt.tcp:
        sp, dp = pkt.tcp.sport, pkt.tcp.dport
        if payload:
            if payload[:5] in (b"HTTP/",) or payload.startswith(HTTP_METHODS):
                return _http(payload)
            if payload[0] == 0x16 and len(payload) > 5 and payload[1] == 0x03:
                sni = _tls_sni(payload)
                return App("TLS", f"ClientHello SNI={sni or '?'}", {"SNI": sni or "", "记录类型": "Handshake"})
            if 80 in (sp, dp):
                return _http(payload) or App("HTTP", f"HTTP 数据 {len(payload)}B")
        if sp == 22 or dp == 22:
            return App("SSH", "SSH 会话")
        if payload and 443 in (sp, dp):
            return App("TLS", f"TLS 记录 {len(payload)}B")
    if pkt.udp:
        sp, dp = pkt.udp.sport, pkt.udp.dport
        if 53 in (sp, dp):
            return _dns(payload)
        if 67 in (sp, dp) or 68 in (sp, dp):
            return App("DHCP", f"DHCP {len(payload)}B")
        if 123 in (sp, dp):
            return App("NTP", "NTP 时间同步")
        if 443 in (sp, dp):
            return App("QUIC", f"QUIC {len(payload)}B")
    return None


def _trim_to_ip_length(pkt: Packet) -> None:
    """按 IP 头里的长度字段裁剪 L4 载荷。

    以太网最小帧是 60 字节，小包会被填充 0。如果直接把 TCP 头之后的字节
    全当载荷，重组出来的流尾部就会多出几个 \\x00（界面上显示成 □）。
    """
    ip = pkt.ip
    if ip is None or ip.total_len <= 0:
        return
    if ip.version == 4:
        ip_payload = ip.total_len - ip.hdr_len
    else:
        # IPv6 的 payload length 不含 40 字节基本头，但包含扩展头
        ip_payload = ip.total_len - max(0, ip.hdr_len - 40)
    if ip_payload <= 0:
        return
    if pkt.tcp is not None:
        want = ip_payload - pkt.tcp.hdr_len
        if 0 <= want < len(pkt.tcp.payload):
            pkt.tcp.payload = pkt.tcp.payload[:want]
    elif pkt.udp is not None:
        want = ip_payload - 8
        if 0 <= want < len(pkt.udp.payload):
            pkt.udp.payload = pkt.udp.payload[:want]


def parse(data: bytes, linktype: int = LINKTYPE_EN10MB, ts: float = 0.0, index: int = 0) -> Packet:
    """把一帧原始字节解析成 Packet。"""
    pkt = Packet(index=index, ts=ts, caplen=len(data), wirelen=len(data),
                 raw=data, linktype=linktype)
    eth, off, etype = _link_offset(data, linktype)
    pkt.eth = eth

    if etype == ETH_ARP:
        pkt.arp = _parse_arp(data, off)
        return pkt

    if etype in (ETH_IPV4, ETH_IPV6) or linktype in (LINKTYPE_RAW, LINKTYPE_NULL):
        version = data[off] >> 4 if len(data) > off else 0
        if version == 4:
            pkt.ip, l4 = _parse_ipv4(data, off)
        elif version == 6:
            pkt.ip, l4 = _parse_ipv6(data, off)
        else:
            return pkt
        if pkt.ip is None:
            return pkt
        if pkt.ip.version == 4 and pkt.ip.total_len:
            pkt.truncated = len(data) - l4 < pkt.ip.total_len - pkt.ip.hdr_len
        if pkt.ip.proto == IPPROTO_TCP:
            pkt.tcp = _parse_tcp(data, l4)
        elif pkt.ip.proto == IPPROTO_UDP:
            pkt.udp = _parse_udp(data, l4)
        elif pkt.ip.proto in (IPPROTO_ICMP, IPPROTO_ICMPV6):
            pkt.icmp = _parse_icmp(data, l4)
        _trim_to_ip_length(pkt)
    pkt.app = _app(pkt)
    return pkt


def hexdump(data: bytes, width: int = 16, limit: int = 4096) -> str:
    """十六进制视图（Wireshark 下方那块的简化版）。"""
    data = data[:limit]
    lines = []
    for i in range(0, len(data), width):
        chunk = data[i:i + width]
        hexs = " ".join(f"{b:02x}" for b in chunk)
        ascii_ = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{i:04x}  {hexs:<{width * 3}}  {ascii_}")
    return "\n".join(lines)
