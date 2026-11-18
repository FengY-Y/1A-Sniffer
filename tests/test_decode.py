"""解析器单元测试：不依赖 root、不依赖 libpcap，直接构造字节流验证。

    python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sniffer import decode                      # noqa: E402
from sniffer.flows import FlowTable             # noqa: E402
from sniffer.pcapfile import read_pcap, write_pcap  # noqa: E402


def mac(s: str) -> bytes:
    return bytes(int(x, 16) for x in s.split(":"))


def ip4(s: str) -> bytes:
    return bytes(int(x) for x in s.split("."))


def eth(dst="00:11:22:33:44:55", src="66:77:88:99:aa:bb", etype=0x0800, payload=b"") -> bytes:
    return mac(dst) + mac(src) + struct.pack("!H", etype) + payload


def ipv4(src="10.0.0.1", dst="10.0.0.2", proto=6, payload=b"", ttl=64, ident=1) -> bytes:
    total = 20 + len(payload)
    hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, total, ident, 0, ttl, proto, 0,
                      ip4(src), ip4(dst))
    return hdr + payload


def tcp(sport=12345, dport=80, payload=b"", flags=0x18, seq=1, ack=1, window=64240) -> bytes:
    offset_flags = (5 << 12) | flags
    return struct.pack("!HHIIHHHH", sport, dport, seq, ack, offset_flags, window, 0, 0) + payload


def udp(sport=5353, dport=53, payload=b"") -> bytes:
    return struct.pack("!HHHH", sport, dport, 8 + len(payload), 0) + payload


def arp(op=1, sha="66:77:88:99:aa:bb", spa="10.0.0.1",
        tha="00:00:00:00:00:00", tpa="10.0.0.2") -> bytes:
    return struct.pack("!HHBBH", 1, 0x0800, 6, 4, op) + mac(sha) + ip4(spa) + mac(tha) + ip4(tpa)


class TestDecode(unittest.TestCase):
    def test_http_get(self):
        body = b"GET /index.html HTTP/1.1\r\nHost: example.com\r\nUser-Agent: curl/8.0\r\n\r\n"
        frame = eth(payload=ipv4(payload=tcp(payload=body)))
        pkt = decode.parse(frame, 1, ts=1700000000.5, index=1)
        self.assertEqual(pkt.proto_name, "TCP")
        self.assertEqual(pkt.src, "10.0.0.1")
        self.assertEqual(pkt.dport, 80)
        self.assertIsNotNone(pkt.app)
        self.assertEqual(pkt.app.proto, "HTTP")
        self.assertEqual(pkt.app.detail["URI"], "/index.html")
        self.assertEqual(pkt.app.detail["Host"], "example.com")
        self.assertIn("10.0.0.1:12345", pkt.summary())

    def test_http_response(self):
        body = b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: 5\r\n\r\nhello"
        pkt = decode.parse(eth(payload=ipv4(proto=6, payload=tcp(sport=80, dport=50000,
                                                               payload=body))), 1)
        self.assertEqual(pkt.app.proto, "HTTP")
        self.assertEqual(pkt.app.detail["状态"], "200 OK")

    def test_dns_query(self):
        q = b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"
        for label in (b"www", b"example", b"com"):
            q += bytes([len(label)]) + label
        q += b"\x00\x00\x01\x00\x01"
        pkt = decode.parse(eth(payload=ipv4(proto=17, payload=udp(payload=q))), 1)
        self.assertEqual(pkt.proto_name, "UDP")
        self.assertIsNotNone(pkt.app)
        self.assertEqual(pkt.app.proto, "DNS")
        self.assertEqual(pkt.app.detail["域名"], "www.example.com")

    def test_arp(self):
        pkt = decode.parse(eth(etype=0x0806, payload=arp()), 1)
        self.assertIsNotNone(pkt.arp)
        self.assertEqual(pkt.arp.sender_ip, "10.0.0.1")
        self.assertIn("ARP", pkt.summary())

    def test_ipv6_tcp(self):
        payload = tcp(sport=443, dport=51000)
        hdr = struct.pack("!IHBB16s16s", 0x60000000, len(payload), 6, 64,
                          bytes.fromhex("20010db8000000000000000000000001"),
                          bytes.fromhex("20010db8000000000000000000000002"))
        pkt = decode.parse(eth(etype=0x86DD, payload=hdr + payload), 1)
        self.assertEqual(pkt.proto_name, "TCP")
        self.assertEqual(pkt.ip.version, 6)
        self.assertEqual(pkt.dport, 51000)

    def test_vlan(self):
        inner = ipv4(payload=tcp())
        frame = (mac("00:11:22:33:44:55") + mac("66:77:88:99:aa:bb")
                 + struct.pack("!HH", 0x8100, 100) + struct.pack("!H", 0x0800) + inner)
        pkt = decode.parse(frame, 1)
        self.assertEqual(pkt.eth.vlans, [100])
        self.assertEqual(pkt.proto_name, "TCP")

    def test_truncated_is_safe(self):
        pkt = decode.parse(b"\x00" * 10, 1)       # 连以太网头都不够
        self.assertEqual(pkt.proto_name, "ETH")
        pkt2 = decode.parse(eth(payload=ipv4(payload=b"\x00\x00")), 1)
        self.assertIsNotNone(pkt2.ip)

    def test_tls_sni(self):
        name = b"www.example.com"
        sni = struct.pack("!H", len(name) + 3) + b"\x00" + struct.pack("!H", len(name)) + name
        exts = struct.pack("!HH", 0x0000, len(sni)) + sni
        body = b"\x03\x03" + b"\x00" * 32 + b"\x00" + b"\x00\x02\x13\x01" + b"\x01\x00"
        body += struct.pack("!H", len(exts)) + exts
        hs = b"\x01" + struct.pack("!I", len(body))[1:] + body
        record = b"\x16\x03\x01" + struct.pack("!H", len(hs)) + hs
        pkt = decode.parse(eth(payload=ipv4(payload=tcp(sport=5000, dport=443, payload=record))), 1)
        self.assertIsNotNone(pkt.app)
        self.assertEqual(pkt.app.proto, "TLS")
        self.assertEqual(pkt.app.detail["SNI"], "www.example.com")

    def test_ethernet_padding_trimmed(self):
        """小包会被补到 60 字节，填充的 0 不能算进 TCP 载荷。"""
        body = b"GET / HTTP/1.1\r\n\r\n"
        frame = eth(payload=ipv4(payload=tcp(payload=body)))
        padded = frame + b"\x00" * max(0, 60 - len(frame))
        pkt = decode.parse(padded, 1)
        self.assertEqual(pkt.tcp.payload, body)
        self.assertNotIn(b"\x00", pkt.tcp.payload)

    def test_hexdump(self):
        text = decode.hexdump(b"ABC")
        self.assertIn("41 42 43", text)


class TestFlows(unittest.TestCase):
    def test_bidirectional_merged(self):
        table = FlowTable()
        syn = decode.parse(eth(payload=ipv4(payload=tcp(flags=0x02))), 1)
        syn_ack = decode.parse(eth(dst="66:77:88:99:aa:bb", src="00:11:22:33:44:55",
                                   payload=ipv4(src="10.0.0.2", dst="10.0.0.1",
                                                payload=tcp(sport=80, dport=12345,
                                                            flags=0x12))), 1)
        table.feed(syn)
        table.feed(syn_ack)
        self.assertEqual(len(table), 1)
        flow = table.flows()[0]
        self.assertEqual(flow.packets, 2)
        self.assertEqual(flow.app, "")            # 还没有应用层
        self.assertEqual(flow.a, ("10.0.0.1", 12345))

    def test_flow_state(self):
        table = FlowTable()
        table.feed(decode.parse(eth(payload=ipv4(payload=tcp(flags=0x02))), 1))
        table.feed(decode.parse(eth(payload=ipv4(payload=tcp(flags=0x11))), 1))
        row = table.rows()[0]
        self.assertEqual(row[7], "CLOSED")


class TestPcapFile(unittest.TestCase):
    def test_roundtrip(self):
        frames = [(1700000000.0, eth(payload=ipv4(payload=tcp()))),
                  (1700000001.25, eth(payload=ipv4(proto=17, payload=udp())))]
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_roundtrip.pcap")
        try:
            write_pcap(path, frames)
            linktype, packets = read_pcap(path)
        finally:
            if os.path.exists(path):
                os.remove(path)
        self.assertEqual(linktype, 1)
        self.assertEqual(len(packets), 2)
        self.assertAlmostEqual(packets[1][0], 1700000001.25, places=5)
        self.assertEqual(packets[0][3][12:14], b"\x08\x00")


if __name__ == "__main__":
    unittest.main()
