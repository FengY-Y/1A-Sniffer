# 实验 1A 嗅探器 —— 起步工程

给《软件与系统安全》实验 1A（带 GUI 的网络嗅探器）准备的一套可运行骨架 + 实施文档。

**先读**：[docs/实验1A-实施方案.md](docs/实验1A-实施方案.md) —— 环境选择（VM vs WSL2）、从哪入手、七天排期、验收清单、报告与视频模板都在里面。

## 这是什么

| 目录 | 内容 |
|---|---|
| `sniffer/pcap.py` | libpcap 的 ctypes 绑定：枚举网卡、打开设备、BPF 过滤、统计、写 pcap |
| `sniffer/decode.py` | 以太网/VLAN/IPv4/IPv6/TCP/UDP/ICMP/ARP 逐层解析 + HTTP/DNS/TLS(SNI) 初判 + hexdump |
| `sniffer/flows.py` | 五元组流表（双向合并、LRU、状态），以及按 `/proc` 做进程归因 |
| `sniffer/reassembly.py` | TCP 双向流重组（按 seq 排序、去重、处理空洞与序号回绕） |
| `sniffer/engine.py` | 抓包线程 + 队列 + 丢包统计；没装 libpcap 时自动退化为纯 Python 离线读文件 |
| `sniffer/cli.py` | 命令行版（先跑通这个） |
| `sniffer/gui.py` | PyQt5 三栏界面（Wireshark 风格） |
| `sniffer/pcapfile.py` | 纯 Python 的 pcap 读写（离线分析 / 造测试数据） |
| `cpp/mini_sniff.c` | 20 行级 C 冒烟程序，验证环境 |
| `scripts/` | Ubuntu 依赖安装、造流量、造 demo pcap |
| `tests/` | 解析器单元测试（不需要 root、不需要 libpcap） |
| `demo/demo.pcap` | 含 ARP/DNS/TCP/HTTP/TLS/ICMP/IPv6 的样例抓包 |

## 虚拟机（已在这台机器上备好）

| 项 | 位置 / 值 |
|---|---|
| 虚拟机配置 | `D:\soft_computer\VMs\sniffer\sniffer.vmx`（4 GB / 2 核 / 25 GB / 双网卡 / 3D 关闭） |
| 网卡 | `ethernet0` = NAT（上网），`ethernet1` = 自定义 `VMnet1`（实验网段 10.10.10.0/24） |
| 安装 ISO | `D:\soft_computer\VMs\iso\ubuntu-24.04.5.1-desktop-amd64.iso` |
| 共享目录 | 主机 `lab1a` → 客户机 `/mnt/hgfs/lab1a`（装了 open-vm-tools 后可见） |
| 管理脚本 | `scripts\vm.cmd status|start|stop|snapshot|clone-victim` |

装完 Ubuntu 后，在虚拟机里跑一条命令即可完成全部配置：

```bash
bash /mnt/hgfs/lab1a/scripts/vm-bootstrap.sh 10.10.10.10
```

它会把依赖装好、把 `ens37` 配成 10.10.10.10、挂共享目录、给 python3 加抓包能力，并跑一遍测例自检。

## 虚拟机（已配置完成，可直接用）

| 机器 | 位置 | 地址 | 状态 |
|---|---|---|---|
| **sniffer** | `D:\soft_computer\VMs\sniffer\sniffer.vmx` | 10.10.10.10（enp0s18） | 依赖已装、`cap_net_raw` 已授、快照 `02-deps` / `03-lab-ready` |
| **victim** | `D:\soft_computer\VMs\victim\victim.vmx` | 10.10.10.20（enp0s18） | sniffer 的完整克隆，MAC/machine-id 已重置、快照 `02-deps` |

- 两台都是 `fy` / `123456`，都装了 `open-vm-tools-desktop`（`vmrun` 可远程执行）、`libpcap-dev`、`pyqt5`、`tcpdump`。
- 实验网段 `10.10.10.0/24` 走 VMware `VMnet1`；主机侧地址 `10.10.10.1`，可直接当第三台机器用。
- 关闭了 3D 加速（`mks.enable3d = FALSE`）：开着 3D 时在这台 Hyper-V 主机上 GNOME 会间歇性卡死。
- 首次开机导入 `open-vm-tools` 后，`/mnt/hgfs/lab1a` 即共享目录；代码已复制到 `~/lab1a`。

常用操作（Windows 上）：

```bat
scripts\vm.cmd status
scripts\vm.cmd start  -Name sniffer
scripts\vm.cmd start  -Name victim
scripts\vm.cmd stop   -Name victim
scripts\vm.cmd snapshot -Name sniffer -Snap 03-demo
```

虚拟机内跑实验：

```bash
cd ~/lab1a
python3 -m sniffer.gui                       # GUI（已免 sudo）
python3 -m sniffer.cli -i enp0s18 -c 5       # 命令行抓包
bash scripts/demo_traffic.sh                 # 造流量
```

## 快速开始（在 Ubuntu 虚拟机里）

```bash
bash scripts/setup_ubuntu.sh

# 1) 不用 root、不用网卡，先验证解析链路
python3 -m sniffer.cli -r demo/demo.pcap --flows

# 2) 真抓包（需要 root 或 cap_net_raw）
sudo python3 -m sniffer.cli -l
sudo python3 -m sniffer.cli -i eth0 -f "tcp port 80" -v

# 3) 看某条流重组后的完整内容（编号来自 --flows 输出）
python3 -m sniffer.cli -r demo/demo.pcap --flows --follow 2

# 4) GUI
bash scripts/run-gui.sh
```

## 测试

```bash
python3 -m unittest discover -s tests -t . -v
```

23 个用例：HTTP 请求/响应、DNS、ARP、IPv6、VLAN、TLS SNI、截断包、流合并、pcap 读写，
以及 TCP 重组（乱序、重传、重叠、空洞、序号回绕、截断、文本/十六进制渲染）。

## 状态说明

- 解析器与流表**已通过单元测试**，`demo/demo.pcap` 可端到端跑通。
- `gui.py` 只做了语法检查，没有在真实 Qt 环境里跑过 —— 第一次运行大概率要调几处布局/信号，这是正常的。
- libpcap 绑定按 Linux x86-64 的 `struct pcap_pkthdr` 布局写；Windows 上要用 Npcap 并改结构体（时间戳是 8 字节），本骨架不保证可用。

## 建议的下一步

1. 跑通 `demo.pcap` → 跑通实时抓包 → 再改 GUI。
2. 想要高分就按文档第 6 节排期走，第 4 天必须有能演示的版本。
3. 报告里的图（架构图、解析流程图、时序图）比代码行数更重要。
