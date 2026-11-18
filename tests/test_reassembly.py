"""TCP 流重组的单元测试：乱序、重传、空洞、序号回绕、文本渲染。

    python3 -m unittest discover -s tests -t . -v
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sniffer.reassembly import StreamBuffer, TcpStream, seq_delta  # noqa: E402


class TestStreamBuffer(unittest.TestCase):
    def test_in_order(self):
        b = StreamBuffer()
        b.feed(1000, b"GET / HTTP/1.1\r\n")
        b.feed(1016, b"Host: a\r\n")
        data, gap = b.read()
        self.assertEqual(data, b"GET / HTTP/1.1\r\nHost: a\r\n")
        self.assertFalse(gap)

    def test_out_of_order(self):
        b = StreamBuffer()
        b.feed(1005, b" world")
        b.feed(1000, b"hello")
        data, gap = b.read()
        self.assertEqual(data, b"hello world")
        self.assertFalse(gap)

    def test_retransmit_no_duplicate(self):
        b = StreamBuffer()
        b.feed(1000, b"abc")
        b.feed(1000, b"abc")          # 完全重传
        b.feed(1003, b"def")
        data, _ = b.read()
        self.assertEqual(data, b"abcdef")

    def test_partial_overlap(self):
        b = StreamBuffer()
        b.feed(1000, b"abcdef")
        b.feed(1003, b"defghi")       # 与前一包重叠 3 字节
        data, _ = b.read()
        self.assertEqual(data, b"abcdefghi")

    def test_gap_stops_delivery(self):
        b = StreamBuffer()
        b.feed(1000, b"abc")
        b.feed(1010, b"xyz")          # 中间缺 7 字节
        data, gap = b.read()
        self.assertEqual(data, b"abc")
        self.assertTrue(gap)

    def test_sequence_wraparound(self):
        b = StreamBuffer()
        base = (1 << 32) - 4
        b.feed(base, b"ABCD")
        b.feed(0, b"EFGH")            # 序号回绕到 0
        data, _ = b.read()
        self.assertEqual(data, b"ABCDEFGH")

    def test_seq_delta(self):
        self.assertEqual(seq_delta(10, 0), 10)
        self.assertEqual(seq_delta(0, 10), -10)
        self.assertEqual(seq_delta((1 << 32) - 1, 0), -1)

    def test_truncation(self):
        b = StreamBuffer(max_bytes=8)
        b.feed(0, b"0123456789ABCDEF")
        data, _ = b.read()
        self.assertEqual(len(data), 8)
        self.assertTrue(b.truncated)


class TestTcpStream(unittest.TestCase):
    def _stream(self):
        s = TcpStream()
        s.feed(True, 1, b"GET /index.html HTTP/1.1\r\n")
        s.feed(True, 28, b"Host: example.com\r\n\r\n")
        s.feed(False, 1, b"HTTP/1.1 200 OK\r\n")
        s.feed(False, 18, b"Content-Length: 2\r\n\r\nhi")
        return s

    def test_render_two_directions(self):
        text = self._stream().render()
        self.assertIn("客户端 → 服务端", text)
        self.assertIn("服务端 → 客户端", text)
        self.assertIn("GET /index.html HTTP/1.1", text)
        self.assertIn("200 OK", text)
        self.assertIn("hi", text)

    def test_render_empty(self):
        self.assertEqual(TcpStream().render(), "（没有可显示的应用层载荷）")

    def test_binary_falls_back_to_hex(self):
        s = TcpStream()
        s.feed(True, 1, bytes(range(0, 32)))     # 不可打印字节
        self.assertIn("00 01 02", s.render())


if __name__ == "__main__":
    unittest.main()
