"""重组正确性校验：拿一份 pcap，检查每条 HTTP 流重组后的一致性。

检查项（每条 HTTP 流）：
    1. 请求行完整（以 HTTP/1.1 结尾，说明没有被截断）
    2. Host 头只出现一次（重传没被拼重复）
    3. 请求头以空行结束（头部完整）
    4. 响应状态是 200
    5. 正文长度 == Content-Length（字节级对齐，最能说明问题）

用法：
    python3 scripts/verify_reassembly.py /tmp/x.pcap
    sudo python3 -m sniffer.cli -i enp0s18 -f "tcp port 8080" -w /tmp/x.pcap   # 先抓一份
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sniffer import decode              # noqa: E402
from sniffer.flows import FlowTable     # noqa: E402
from sniffer.pcapfile import read_pcap  # noqa: E402


def check(path: str) -> int:
    linktype, packets = read_pcap(path)
    table = FlowTable()
    for i, (ts, _caplen, _wirelen, data) in enumerate(packets):
        table.feed(decode.parse(data, linktype, ts=ts, index=i + 1))

    print(f"文件={path}  包数={len(packets)}  流数={len(table)}")
    passed = failed = 0

    for n, flow in enumerate(table.flows(), 1):
        if flow.stream is None:
            continue
        up, up_gap = flow.stream.up.read()
        down, down_gap = flow.stream.down.read()
        if not up.startswith((b"GET ", b"POST ")):
            continue

        req = up.replace(b"\r\n", b"\n").decode("utf-8", "replace")
        resp = down.replace(b"\r\n", b"\n").decode("utf-8", "replace")

        checks = [
            ("请求行完整", req.splitlines()[0].endswith("HTTP/1.1")),
            ("Host 头唯一", req.count("\nHost:") == 1),
            ("请求头以空行结束", "\n\n" in req),
            ("响应 200", re.match(r"HTTP/1\.[01] 200", resp) is not None),
        ]
        m = re.search(r"Content-Length:\s*(\d+)", resp)
        if m:
            body = resp.split("\n\n", 1)[1] if "\n\n" in resp else ""
            want, got = int(m.group(1)), len(body.encode("utf-8", "replace"))
            checks.append((f"正文 {got}/{want}", got == want))

        bad = [name for name, ok in checks if not ok]
        state = "全部通过" if not bad else "FAIL " + ", ".join(bad)
        print(f"  流{n}: 上{len(up)}B 下{len(down)}B "
              f"gap={up_gap},{down_gap} -> {state}")
        passed += sum(1 for _, ok in checks if ok)
        failed += len(bad)

    print(f"\nPASS={passed} FAIL={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(check(sys.argv[1]))
