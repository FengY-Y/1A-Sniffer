"""命令行版嗅探器：先把这个跑通，再做 GUI。

用法：
    sudo python3 -m sniffer.cli -l                       # 列出网卡
    sudo python3 -m sniffer.cli -i eth0                  # 抓所有包
    sudo python3 -m sniffer.cli -i eth0 -f "tcp port 80"  # BPF 过滤
    sudo python3 -m sniffer.cli -i eth0 -c 20 -v         # 抓 20 个包并打印详情
    python3 -m sniffer.cli -r test.pcap                  # 离线读文件，不需要 root
"""
from __future__ import annotations

import argparse
import queue
import sys
import time

from . import decode
from .pcap import PcapError, list_devices


def _fmt_ts(ts: float) -> str:
    lt = time.localtime(ts)
    return time.strftime("%H:%M:%S", lt) + f".{int((ts % 1) * 1000):03d}"


HEADER = f"{'No.':>5}  {'Time':<13} {'Source':<22} {'Destination':<22} {'Proto':<6} {'Len':>5}  Info"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="实验 1A 最小可用嗅探器（CLI）")
    ap.add_argument("-l", "--list", action="store_true", help="列出可用网卡")
    ap.add_argument("-i", "--iface", help="网卡名，例如 eth0 / enp0s3")
    ap.add_argument("-r", "--read", help="读取 pcap 文件（离线模式）")
    ap.add_argument("-f", "--filter", default="", help="BPF 过滤表达式")
    ap.add_argument("-c", "--count", type=int, default=0, help="抓够 N 个包就退出")
    ap.add_argument("-w", "--write", help="把抓到的包另存为 pcap")
    ap.add_argument("-v", "--verbose", action="store_true", help="打印每个包的详细字段")
    ap.add_argument("--no-promisc", action="store_true", help="关闭混杂模式")
    ap.add_argument("--flows", action="store_true", help="退出时打印流统计")
    args = ap.parse_args(argv)

    if args.list:
        for name, desc in list_devices():
            print(f"{name:<20} {desc}")
        return 0

    if not args.iface and not args.read:
        ap.error("要么用 -i 指定网卡，要么用 -r 指定 pcap 文件")

    from .engine import CaptureEngine        # 延迟导入，--list 时不需要 libpcap

    engine = CaptureEngine(
        device=args.iface,
        path=args.read,
        bpf=args.filter,
        promisc=not args.no_promisc,
        write_path=args.write,
    )
    try:
        engine.start()
    except Exception as e:
        print(f"[!] 启动失败: {e}", file=sys.stderr)
        return 1

    print(HEADER)
    print("-" * len(HEADER))
    shown, started = 0, time.time()
    try:
        while True:
            try:
                pkt = engine.queue.get(timeout=0.2)
            except queue.Empty:
                if engine.finished:
                    break
                continue
            shown += 1
            print(f"{pkt.index:>5}  {_fmt_ts(pkt.ts):<13} {pkt.src:<22} {pkt.dst:<22} "
                  f"{pkt.proto_name:<6} {pkt.wirelen:>5}  {pkt.summary()}")
            if args.verbose:
                for k, v in pkt.detail_rows():
                    print(f"        {k:<16} {v}")
                print(decode.hexdump(pkt.raw, limit=128))
            if args.count and shown >= args.count:
                break
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop()
        engine.join(timeout=2.0)

    elapsed = max(1e-6, time.time() - started)
    print("-" * len(HEADER))
    print(f"共 {engine.total_packets} 个包 / {engine.total_bytes} 字节，"
          f"用时 {elapsed:.2f}s，内核丢包 {engine.kernel_dropped}，队列丢包 {engine.queue_dropped}")
    if engine.error:
        print(f"[!] {engine.error}", file=sys.stderr)
    if args.flows:
        flows = engine.flow_objects()
        print(f"\n共 {len(flows)} 条流：")
        print(f"{'Proto':<6} {'Client':<24} {'Server':<24} {'App':<6} {'Pkts':>5} "
              f"{'Bytes':>8}  {'State':<7} 进程")
        for f in flows[:50]:
            r = f.row()
            print(f"{r[0]:<6} {r[1]:<24} {r[2]:<24} {r[3]:<6} {r[4]:>5} {r[5]:>8}  "
                  f"{r[7]:<7} {r[8]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
