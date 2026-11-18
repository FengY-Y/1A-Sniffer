"""嗅探器自测：把实验要求逐条跑一遍，输出 PASS/FAIL 表。

覆盖：
    1. 网卡枚举
    2. 实时抓包（全量）
    3. BPF 过滤：icmp / tcp port 8080 / host+tcp / 只听 SYN
    4. 非法过滤表达式不崩溃
    5. 抓包落盘 pcap，再离线读回来，包数一致
    6. 流追踪：五元组合并、应用层识别
    7. 进程归因（需要 root）
    8. TCP 重组：HTTP 请求行、Content-Length 与正文长度对齐
    9. 统计信息（内核丢包）可读

用法（建议 root，进程归因才完整）：
    sudo SNIFFER_IFACE=enp0s18 python3 scripts/selftest.py
需要同时有流量经过该网卡，否则过滤项会因没包而判为失败。
"""
from __future__ import annotations

import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sniffer import decode                      # noqa: E402
from sniffer.engine import CaptureEngine        # noqa: E402
from sniffer.pcap import PcapError, list_devices  # noqa: E402
from sniffer.pcapfile import read_pcap          # noqa: E402

DEV = os.environ.get("SNIFFER_IFACE", "enp0s18")
RESULTS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def capture(bpf: str, seconds: float = 3.0) -> CaptureEngine:
    eng = CaptureEngine(device=DEV, bpf=bpf)
    eng.start()
    time.sleep(seconds)
    eng.queue.empty()
    eng.stop()
    eng.join(timeout=3)
    return eng


def drain(eng: CaptureEngine):
    out = []
    while True:
        try:
            out.append(eng.queue.get_nowait())
        except Exception:
            break
    return out


def main() -> int:
    print(f"设备：{DEV}    用户：{'root' if os.geteuid() == 0 else 'non-root'}\n")

    # 1. 设备枚举
    try:
        devs = list_devices()
        check("网卡枚举", bool(devs), f"{len(devs)} 块")
    except PcapError as e:
        check("网卡枚举", False, str(e))

    # 2. 非法过滤表达式
    eng = CaptureEngine(device=DEV, bpf="this is not a valid filter")
    eng.start()
    time.sleep(1.0)
    eng.stop()
    eng.join(timeout=2)
    check("非法 BPF 不崩溃且报错", bool(eng.error), str(eng.error)[:40])

    # 3. 全量抓包
    eng = capture("", 3.0)
    pkts = drain(eng)
    check("实时抓包", len(pkts) > 0, f"{len(pkts)} 包")
    check("统计可读", isinstance(eng.kernel_dropped, int),
          f"内核丢包={eng.kernel_dropped} 队列丢包={eng.queue_dropped}")

    # 4. BPF 过滤：icmp
    eng = capture("icmp", 3.0)
    pkts = drain(eng)
    check("过滤 icmp", bool(pkts) and all(p.icmp is not None for p in pkts),
          f"{len(pkts)} 包")

    # 5. BPF 过滤：tcp port 8080
    eng = capture("tcp port 8080", 4.0)
    pkts = drain(eng)
    ok = bool(pkts) and all(8080 in (p.sport, p.dport) for p in pkts)
    check("过滤 tcp port 8080", ok, f"{len(pkts)} 包")

    # 6. BPF 逻辑演算：host + 端口组合（and）
    eng = capture("host 10.10.10.1 and tcp port 8080", 4.0)
    host_pkts = drain(eng)
    ok = bool(host_pkts) and all(
        8080 in (p.sport, p.dport) and "10.10.10.1" in (p.src, p.dst)
        for p in host_pkts)
    check("过滤 host + 端口（and 组合）", ok, f"{len(host_pkts)} 包")

    # 7. 只听 SYN（tcp[tcpflags] 语法）
    eng = capture("tcp[tcpflags] & tcp-syn != 0", 4.0)
    pkts = drain(eng)
    ok = bool(pkts) and all(p.tcp is not None and (p.tcp.flags & 0x02) for p in pkts)
    check("过滤 TCP SYN", ok, f"{len(pkts)} 包")

    # 8. 流追踪 + 应用层识别 + 进程归因 + 重组
    eng = capture("tcp port 8080", 5.0)
    flows = eng.flow_objects()
    http_flows = [f for f in flows if f.app == "HTTP"]
    check("流追踪聚合", bool(flows), f"{len(flows)} 条流")
    check("应用层识别 HTTP", bool(http_flows), f"{len(http_flows)} 条")

    proc = [f.process for f in flows if f.process]
    check("进程归因", bool(proc), proc[0] if proc else "（非 root 或没有本地监听）")

    reasm_ok, reasm_detail = False, "没有带载荷的流"
    for f in flows:
        if f.stream is None:
            continue
        up, _ = f.stream.up.read()
        down, _ = f.stream.down.read()
        req = up.replace(b"\r\n", b"\n").decode("utf-8", "replace")
        resp = down.replace(b"\r\n", b"\n").decode("utf-8", "replace")
        if not req.startswith(("GET ", "POST ")):
            continue
        line_ok = req.splitlines()[0].endswith("HTTP/1.1")
        m = re.search(r"Content-Length:\s*(\d+)", resp)
        len_ok = True
        if m and "\n\n" in resp:
            body = resp.split("\n\n", 1)[1]
            len_ok = len(body.encode("utf-8", "replace")) == int(m.group(1))
        clean = b"\x00" not in up and b"\x00" not in down
        reasm_ok = line_ok and len_ok and clean
        reasm_detail = (f"上行{len(up)}B 下行{len(down)}B "
                        f"请求行={'OK' if line_ok else 'NG'} "
                        f"长度={'OK' if len_ok else 'NG'} "
                        f"无填充={'OK' if clean else 'NG'}")
        break
    check("TCP 重组", reasm_ok, reasm_detail)

    # 9. 落盘 + 离线读回
    path = "/tmp/selftest.pcap"
    if os.path.exists(path):
        os.remove(path)
    eng = CaptureEngine(device=DEV, bpf="tcp port 8080", write_path=path)
    eng.start()
    time.sleep(4.0)
    eng.stop()
    eng.join(timeout=3)
    live_count = eng.total_packets
    try:
        linktype, stored = read_pcap(path)
        check("保存 pcap 并读回",
              len(stored) == live_count and len(stored) > 0,
              f"写入 {live_count} 包 / 读回 {len(stored)} 包")
        check("链路类型正确", linktype == 1, f"linktype={linktype}")
    except Exception as e:                       # noqa: BLE001
        check("保存 pcap 并读回", False, str(e))

    passed = sum(1 for _, ok in RESULTS if ok)
    total = len(RESULTS)
    print(f"\n合计：{passed}/{total} 通过")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
