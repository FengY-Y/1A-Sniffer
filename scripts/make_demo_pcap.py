"""生成一个包含常见协议样例的 pcap，用来做界面截图 / 离线自测。

    python3 scripts/make_demo_pcap.py demo/demo.pcap
"""
from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sniffer.pcapfile import write_pcap  # noqa: E402

CLIENT_MAC = bytes.fromhex("080027aabb01")
SERVER_MAC = bytes.fromhex("080027ccdd02")
CLIENT_IP = bytes([192, 168, 56, 10])
SERVER_IP = bytes([93, 184, 216, 34])
GATEWAY_IP = bytes([192, 168, 56, 1])


def eth(dst, src, etype, payload=b""):
    return dst + src + struct.pack("!H", etype) + payload


def ipv4(src, dst, proto, payload, ttl=64, ident=1, flags=0x4000):
    return struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(payload), ident, flags, ttl,
                       proto, 0, src, dst) + payload


def tcp(sport, dport, seq, ack, flags, payload=b"", window=64240):
    return struct.pack("!HHIIHHHH", sport, dport, seq, ack, (5 << 12) | flags,
                       window, 0, 0) + payload


def udp(sport, dport, payload):
    return struct.pack("!HHHH", sport, dport, 8 + len(payload), 0) + payload


def dns_query(txid, name, qtype=1):
    q = struct.pack("!HHHHHH", txid, 0x0100, 1, 0, 0, 0)
    for label in name.split("."):
        q += bytes([len(label)]) + label.encode()
    return q + b"\x00" + struct.pack("!HH", qtype, 1)


def dns_response(txid, name, ip):
    q = dns_query(txid, name)
    ans = b"\xc0\x0c" + struct.pack("!HHIH", 1, 1, 60, 4) + ip
    # 头部 12 字节（txid + flags + qd/an/ns/ar），后面接原始问题段 q[12:]
    return struct.pack("!HHHHHH", txid, 0x8180, 1, 1, 0, 0) + q[12:] + ans


def tls_client_hello(sni: str) -> bytes:
    exts = b""
    name = sni.encode()
    sni_body = struct.pack("!H", len(name) + 3) + b"\x00" + struct.pack("!H", len(name)) + name
    exts += struct.pack("!HH", 0x0000, len(sni_body)) + sni_body
    exts += struct.pack("!HH", 0x000A, 4) + b"\x00\x02\x00\x1d"     # supported_groups
    body = b"\x03\x03" + os.urandom(32) + b"\x00"                   # version + random + sid
    body += b"\x00\x04\x13\x01\x13\x02"                             # cipher suites
    body += b"\x01\x00"                                             # compression
    body += struct.pack("!H", len(exts)) + exts
    hs = b"\x01" + struct.pack("!I", len(body))[1:] + body
    return b"\x16\x03\x01" + struct.pack("!H", len(hs)) + hs


def build():
    frames = []
    t = 1700000000.0

    def add(dt, frame):
        nonlocal t
        t += dt
        frames.append((t, frame))

    # 1. ARP 请求：客户端问网关的 MAC
    arp_req = struct.pack("!HHBBH", 1, 0x0800, 6, 4, 1) + CLIENT_MAC + CLIENT_IP + \
        b"\x00" * 6 + GATEWAY_IP
    add(0.001, eth(b"\xff" * 6, CLIENT_MAC, 0x0806, arp_req))
    arp_rep = struct.pack("!HHBBH", 1, 0x0800, 6, 4, 2) + bytes.fromhex("080027112233") + \
        GATEWAY_IP + CLIENT_MAC + CLIENT_IP
    add(0.002, eth(CLIENT_MAC, bytes.fromhex("080027112233"), 0x0806, arp_rep))

    # 2. DNS 查询 + 应答
    add(0.010, eth(SERVER_MAC, CLIENT_MAC, 0x0800,
                   ipv4(CLIENT_IP, bytes([192, 168, 56, 1]), 17,
                        udp(53124, 53, dns_query(0x1234, "example.com")))))
    add(0.012, eth(CLIENT_MAC, SERVER_MAC, 0x0800,
                   ipv4(bytes([192, 168, 56, 1]), CLIENT_IP, 17,
                        udp(53, 53124, dns_response(0x1234, "example.com", SERVER_IP)))))

    # 3. TCP 三次握手
    cport = 49876
    add(0.020, eth(SERVER_MAC, CLIENT_MAC, 0x0800,
                   ipv4(CLIENT_IP, SERVER_IP, 6, tcp(cport, 80, 1000, 0, 0x02))))
    add(0.040, eth(CLIENT_MAC, SERVER_MAC, 0x0800,
                   ipv4(SERVER_IP, CLIENT_IP, 6, tcp(80, cport, 5000, 1001, 0x12))))
    add(0.041, eth(SERVER_MAC, CLIENT_MAC, 0x0800,
                   ipv4(CLIENT_IP, SERVER_IP, 6, tcp(cport, 80, 1001, 5001, 0x10))))

    # 4. HTTP 请求 / 响应
    req = (b"GET /index.html HTTP/1.1\r\nHost: example.com\r\n"
           b"User-Agent: curl/8.5.0\r\nAccept: */*\r\n\r\n")
    add(0.050, eth(SERVER_MAC, CLIENT_MAC, 0x0800,
                   ipv4(CLIENT_IP, SERVER_IP, 6, tcp(cport, 80, 1001, 5001, 0x18, req))))
    body = b"<html><body><h1>hello sniffer</h1></body></html>"
    resp = (b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: "
            + str(len(body)).encode() + b"\r\n\r\n" + body)
    add(0.060, eth(CLIENT_MAC, SERVER_MAC, 0x0800,
                   ipv4(SERVER_IP, CLIENT_IP, 6, tcp(80, cport, 5001, 1001 + len(req), 0x18, resp))))

    # 5. HTTPS：只能看到 SNI
    add(0.200, eth(SERVER_MAC, CLIENT_MAC, 0x0800,
                   ipv4(CLIENT_IP, SERVER_IP, 6,
                        tcp(49877, 443, 2000, 0, 0x02))))
    add(0.230, eth(SERVER_MAC, CLIENT_MAC, 0x0800,
                   ipv4(CLIENT_IP, SERVER_IP, 6,
                        tcp(49877, 443, 2001, 1, 0x18, tls_client_hello("www.example.com")))))

    # 6. ICMP ping
    icmp = struct.pack("!BBHHH", 8, 0, 0, 1, 1) + b"abcdefghijklmnop"
    add(0.300, eth(SERVER_MAC, CLIENT_MAC, 0x0800,
                   ipv4(CLIENT_IP, SERVER_IP, 1, icmp, ttl=64)))
    icmp_rep = struct.pack("!BBHHH", 0, 0, 0, 1, 1) + b"abcdefghijklmnop"
    add(0.301, eth(CLIENT_MAC, SERVER_MAC, 0x0800,
                   ipv4(SERVER_IP, CLIENT_IP, 1, icmp_rep, ttl=54)))

    # 7. IPv6 上的 TCP
    v6_payload = tcp(52000, 443, 3000, 0, 0x02)
    v6_hdr = struct.pack("!IHBB", 0x60000000, len(v6_payload), 6, 64) + \
        bytes.fromhex("20010db8000000000000000000000010") + \
        bytes.fromhex("20010db8000000000000000000000020")
    add(0.400, eth(SERVER_MAC, CLIENT_MAC, 0x86DD, v6_hdr + v6_payload))

    return frames


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "demo/demo.pcap"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    frames = build()
    write_pcap(out, frames, linktype=1)
    print(f"写入 {out}，共 {len(frames)} 个包")
