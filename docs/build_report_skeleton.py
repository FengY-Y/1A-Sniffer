"""生成《实验 1A 报告》骨架 docx。

    python build_report_skeleton.py

结构按“目标 → 设计 → 实现 → 测试 → 问题 → 分析 → 不足”组织，
正文用灰色提示文字，图表位置写成【占位】，直接往里填内容即可。
"""
from __future__ import annotations

import os
import re

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "实验1A-报告-骨架.docx")

BODY_FONT = "微软雅黑"
CODE_FONT = "Consolas"
ACCENT = RGBColor(0x1F, 0x38, 0x64)
GRAY = RGBColor(0x66, 0x66, 0x66)
HINT = RGBColor(0x8A, 0x6D, 0x3B)
_TABLE_NO = [0]


# ---------------------------------------------------------------- 基础工具
def set_run(run, size=10.5, bold=False, color=None, italic=False,
            name=BODY_FONT, eastasia=None):
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    if color:
        run.font.color.rgb = color
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), name)
    rfonts.set(qn("w:hAnsi"), name)
    rfonts.set(qn("w:eastAsia"), eastasia or name)


def shade(el, fill):
    pr = el._p.get_or_add_pPr() if hasattr(el, "_p") else el._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    pr.append(shd)


def h1(doc, text):
    p = doc.add_heading(level=1)
    p.paragraph_format.space_before = Pt(16)
    p.paragraph_format.space_after = Pt(6)
    set_run(p.add_run(text), size=15, bold=True, color=ACCENT)
    ppr = p._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "8")
    bottom.set(qn("w:color"), "C9D3E3")
    borders.append(bottom)
    ppr.append(borders)


def h2(doc, text):
    p = doc.add_heading(level=2)
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    set_run(p.add_run(text), size=12, bold=True, color=RGBColor(0x2E, 0x4A, 0x7A))


def h3(doc, text):
    p = doc.add_heading(level=3)
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)
    set_run(p.add_run(text), size=10.5, bold=True, color=RGBColor(0x3A, 0x3A, 0x3A))


def body(doc, text, hint=False, size=10.5):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(5)
    p.paragraph_format.line_spacing = 1.3
    if text.rstrip().endswith(("：", ":")):
        p.paragraph_format.keep_with_next = True
    set_run(p.add_run(text), size=size,
            color=HINT if hint else None, italic=hint)
    return p


def bullets(doc, items, size=10.5):
    for it in items:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.25
        set_run(p.add_run(it), size=size)


def code(doc, text, size=9):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(3)
    pf.space_after = Pt(5)
    pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
    pf.left_indent = Cm(0.4)
    pf.keep_together = True
    shade(p, "F4F5F7")
    ppr = p._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    for side in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), "D9DCE1")
        borders.append(el)
    ppr.append(borders)
    for i, line in enumerate(text.split("\n")):
        if i:
            p.add_run().add_break()
        set_run(p.add_run(line), size=size, name=CODE_FONT, eastasia=BODY_FONT)


def slot(doc, text):
    """图表占位：虚线框 + 【…】"""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(8)
    shade(p, "FAF7EF")
    ppr = p._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    for side in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "dashed")
        el.set(qn("w:sz"), "6")
        el.set(qn("w:color"), "C7B394")
        borders.append(el)
    ppr.append(borders)
    set_run(p.add_run(f"【{text}】"), size=9.5, color=HINT, italic=True)


def caption(doc, text):
    """表题自动编号：按出现顺序重排，插入新表时不用手改编号。"""
    if text.startswith("表"):
        _TABLE_NO[0] += 1
        text = re.sub(r"^表\s*\d*\s*", f"表 {_TABLE_NO[0]}  ", text)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(8)
    set_run(p.add_run(text), size=9, color=GRAY)


def table(doc, headers, rows, widths, size=9, first_col_bold=False):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    tblPr = t._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for side, val in (("top", 30), ("bottom", 30), ("left", 90), ("right", 90)):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    try:
        tblPr.insert_element_before(mar, "w:tblLook")
    except Exception:
        tblPr.append(mar)

    for i, h in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.0
        set_run(p.add_run(h), size=size, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
        shade(cell, "1F3864")

    for r_i, row in enumerate(rows):
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.0
            set_run(p.add_run(str(val)), size=size, bold=(first_col_bold and i == 0))
            if r_i % 2 == 1:
                shade(cells[i], "F2F5FA")

    for idx, row in enumerate(t.rows):
        trPr = row._tr.get_or_add_trPr()
        trPr.append(OxmlElement("w:cantSplit"))
        if idx == 0:
            trPr.append(OxmlElement("w:tblHeader"))
        # 除最后一行外都 keep_with_next：整张表尽量不跨页，
        # 避免出现“下一页只剩一行”的孤行
        if idx < len(t.rows) - 1:
            for cell in row.cells:
                for p in cell.paragraphs:
                    p.paragraph_format.keep_with_next = True
        for i, w in enumerate(widths):
            row.cells[i].width = Cm(w)
    return t


# ---------------------------------------------------------------- 正文
def build():
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.top_margin = Cm(2.2)
    sec.bottom_margin = Cm(2.0)
    sec.left_margin = Cm(2.2)
    sec.right_margin = Cm(2.2)

    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = Pt(10.5)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), BODY_FONT)

    # 页脚
    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run(fp.add_run("软件与系统安全 · 实验 1A · 第 "), size=8.5, color=GRAY)
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    fp._p.append(fld)
    set_run(fp.add_run(" 页"), size=8.5, color=GRAY)

    # 标题
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(10)
    set_run(p.add_run("实验 1A  带 GUI 的网络嗅探器设计与实现"), size=22, bold=True, color=ACCENT)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    set_run(p.add_run("软件与系统安全 · 实验报告"), size=12, color=GRAY)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(14)
    set_run(p.add_run("姓名：____________　　学号：________________　　日期：____________"),
            size=10.5, color=GRAY)

    slot(doc, "在这里放一张程序运行截图（抓包列表 + 协议树 + 十六进制），作为封面图")

    # 0 摘要
    h1(doc, "0  摘要与完成情况")
    body(doc, "本实验实现了一个带图形界面的网络嗅探器：基于 libpcap 在链路层抓包，"
              "逐层解析到应用层，支持 BPF 过滤、TCP 流追踪、双向流重组与进程归因。"
              "界面为 Wireshark 风格的三栏布局（包列表 / 协议树 / 十六进制），另设流追踪页。", hint=True)
    table(doc,
          ["实验要求", "出处", "完成情况"],
          [["实现 NPS：真的把包抓上来", "p9（否则不及格）", "完成，实测 108 包/3 秒"],
           ["尽量完善 NPA：逐层解析", "p9（否则分不高）", "完成，解析到应用层并识别 HTTP/DNS/TLS"],
           ["带 GUI", "p5 标题", "完成，PyQt5 三栏界面"],
           ["协议过滤，支持逻辑演算", "p14", "完成，BPF 走内核，and/or/not 均可用"],
           ["流追踪：IP+Port 的 TCP 流", "p14（加分）", "完成，双向合并 + LRU"],
           ["流追踪：某进程的所有 TCP 流", "p14（进阶）", "完成，/proc 归因，需 root"],
           ["保存/读取 pcap", "—", "完成，写回读包数一致"],
           ["TCP 流重组（扩展）", "p9 的思考题", "完成，HTTP 请求/响应完整还原"]],
          [6.2, 3.6, 6.8])
    caption(doc, "表 1  实验要求与完成情况")

    h2(doc, "0.1  报告结构")
    bullets(doc, [
        "第 1 节  需求分析：NPS 与 NPA 的边界、功能与非功能需求；",
        "第 2 节  总体设计：分层架构、线程模型、模块划分与关键取舍；",
        "第 3 节  关键技术：libpcap 参数、BPF 过滤、协议解析、流追踪、TCP 重组；",
        "第 4 节  测试与结果：14 项端到端自测、25 项重组一致性检查、第三方流量捕获；",
        "第 5 节  遇到的问题与解决：10 个实际踩坑，按“现象→根因→解决→启示”记录；",
        "第 6 节  安全分析：抓包层次、HTTPS 可见性边界、交换式网络与权限边界；",
        "第 7 节  不足与改进方向。",
    ], size=10)

    h2(doc, "0.2  开发过程")
    body(doc, "按“先证明通路、再补功能、最后做验证”的顺序推进，每一步都有可检查的产出：", hint=True)
    table(doc,
          ["阶段", "主要工作", "验证方式"],
          [["① 环境", "VMware 建虚拟机、Ubuntu、依赖、双网卡（NAT + VMnet1）",
            "两机互通，客户端能上网装包"],
           ["② 冒烟", "用 libpcap 打开网卡读前 10 个包", "能看到 ping 的 ICMP"],
           ["③ 解析", "以太网/VLAN/IPv4/IPv6/TCP/UDP/ICMP/ARP 逐层解析",
            "CLI 打印摘要与详情"],
           ["④ 界面", "抓包线程 + 队列 + 三栏界面", "界面滚动不卡，点包出详情"],
           ["⑤ 流", "五元组聚合、LRU、进程归因", "一条连接只出现一条流"],
           ["⑥ 重组", "seq 排序、去重、空洞、跟随流", "HTTP 请求与响应完整还原"],
           ["⑦ 验证", "端到端自测 14 项、重组一致性 25 项", "全部通过"]],
          [2.0, 9.4, 5.0])
    caption(doc, "表 2  开发阶段与产出")

    # 1 需求分析
    h1(doc, "1  需求分析")
    h2(doc, "1.1  NPS 与 NPA 的区别")
    body(doc, "课件 p9 明确指出：Wireshark 这类工具属于 Network Protocol Analyzer（NPA），"
              "而本次要实现的 Network Packet Sniffer（NPS）只负责“把流量抓上来”。"
              "两者的分界在于是否理解协议语义。本实验的定位是：NPS 必须可靠，NPA 尽量完善。", hint=True)
    h2(doc, "1.2  功能需求")
    table(doc,
          ["编号", "需求", "验收方式"],
          [["F1", "枚举网卡、选择网卡、开始/停止抓包", "下拉框可见多块网卡，抓包计数随流量增长"],
           ["F2", "按 BPF 表达式过滤（协议、端口、主机、逻辑组合）", "过滤后列表中每个包都满足条件"],
           ["F3", "逐层解析并展示字段", "点任一包显示以太网/IP/TCP/应用层字段"],
           ["F4", "原始字节十六进制视图", "与所选包首字节一致"],
           ["F5", "按五元组聚合流并统计", "一条连接只出现一条流"],
           ["F6", "把流还原成完整应用层内容", "HTTP 请求行与正文完整"],
           ["F7", "保存为 pcap 并可被 Wireshark 打开", "读回包数与写入一致"],
           ["F8", "显示收包/丢包统计", "状态栏可读，测试时丢包为 0"]],
          [1.4, 8.4, 6.6])
    caption(doc, "表 2  功能需求")
    h2(doc, "1.3  非功能需求")
    bullets(doc, [
        "健壮性：畸形包、截断包、非法过滤表达式都不能让程序崩溃；",
        "实时性：抓包不能阻塞界面，界面刷新不能拖慢抓包；",
        "可移植性：Linux 下依赖 libpcap，无 libpcap 时仍能离线分析 pcap；",
        "可测试性：解析、重组等纯逻辑模块要能脱离网卡和 root 做单元测试。",
    ])

    # 2 总体设计
    h1(doc, "2  总体设计")
    h2(doc, "2.1  架构")
    body(doc, "分四层：抓包层（libpcap）、解析层（纯字节处理）、状态层（流表与重组缓冲）、展示层（CLI/GUI）。"
              "上层只依赖下层的数据结构，不反向依赖，便于单独测试。", hint=True)
    slot(doc, "画一张分层架构图：GUI/CLI → 抓包线程 → decode → flows/reassembly → libpcap → 网卡")
    h2(doc, "2.2  线程模型")
    body(doc, "pcap_next_ex 默认阻塞（超时 100 ms），放在 GUI 主线程会让界面卡死。"
              "因此：抓包线程只做“读包 → 解析 → 入队”，界面用 60 ms 定时器批量出队渲染。", hint=True)
    code(doc, "抓包线程:  pcap_next_ex → decode.parse → FlowTable.feed(重组/归因) → Queue\n"
              "界面线程:  QTimer(60ms) → 一次取最多 4000 个 → 插入表格模型")
    h2(doc, "2.3  模块职责")
    table(doc,
          ["模块", "职责", "关键点"],
          [["pcap.py", "libpcap 的 ctypes 绑定", "设备枚举、激活参数、BPF 编译、dump"],
           ["decode.py", "以太网/VLAN/IP/TCP/UDP/ICMP/ARP 解析", "任何越界都返回 None，不抛异常"],
           ["flows.py", "五元组流表、LRU、进程归因", "规范化 key 让双向合并"],
           ["reassembly.py", "TCP 双向流重组", "seq 定位、去重、空洞、回绕"],
           ["engine.py", "抓包线程、队列、统计", "线程安全、丢包计数"],
           ["cli.py / gui.py", "两种展示层", "GUI 含协议树、十六进制、跟随流"]],
          [3.0, 6.0, 7.4])
    caption(doc, "表 3  模块职责")
    h2(doc, "2.4  关键设计决策")
    bullets(doc, [
        "自己写 libpcap 的 ctypes 绑定，而不是用 scapy 之类的库——这样才真正对应“调用 libpcap”的要求，"
        "也便于解释每个参数的作用；",
        "选择 Python：本实验的瓶颈不在解析而在 IO，Python 足够；同时把解析、重组写成纯函数，便于单测；",
        "过滤一律下推给内核（BPF），用户态不再做二次过滤，避免大流量下的无谓拷贝；",
        "状态类信息（进程归属）在流存活期间就记录下来，而不是等结束时再查。",
    ])

    # 3 关键技术
    h1(doc, "3  关键技术实现")
    h2(doc, "3.1  libpcap 使用")
    body(doc, "打开设备的参数直接决定抓包质量：", hint=True)
    code(doc, "pcap_create → set_snaplen(262144) → set_promisc(1)\n"
              "           → set_timeout(100)   → set_buffer_size(32MB) → activate")
    bullets(doc, [
        "snaplen：太小会截断大包，262144 足够容纳 jumbo frame；",
        "promisc：让网卡接收所有帧；但在交换式网络中能收到多少取决于拓扑（见 6.3）；",
        "buffer_size：内核环形缓冲，抓包丢包最常见的原因是这里太小；",
        "timeout：影响 next_ex 的返回粒度，进而影响界面刷新与 CPU 占用。",
    ])
    h2(doc, "3.2  BPF 过滤")
    body(doc, "表达式交给 libpcap 编译成内核过滤器，不匹配的包在进入用户态之前就被丢弃。", hint=True)
    code(doc, "pcap_compile(pcap, &prog, \"host 10.10.10.1 and tcp port 8080\", 1, PCAP_NETMASK_UNKNOWN)\n"
              "pcap_setfilter(pcap, &prog)   // 失败则报错，不静默\n"
              "pcap_freecode(&prog)")
    table(doc,
          ["表达式", "含义"],
          [["tcp port 8080", "只看某个服务的会话"],
           ["icmp", "只看 ping"],
           ["host 10.10.10.1 and tcp", "主机 + 协议的与运算"],
           ["tcp[tcpflags] & tcp-syn != 0", "只看建连请求（按位取标志）"],
           ["not udp port 1900 and not arp", "排除 SSDP 噪声与 ARP"]],
          [7.0, 9.4])
    caption(doc, "表 4  常用过滤表达式")
    body(doc, "为什么必须在内核过滤：用户态过滤等于先把所有包拷上来再挑，"
              "流量大时 CPU 与内存拷贝先成为瓶颈，正是课件 p21–25 讨论的问题。", hint=True)
    h2(doc, "3.3  协议解析")
    body(doc, "解析器按层拆分，每层只关心自己的头部长度，任何字段越界都返回 None 并保留已解析的部分。"
              "几个容易出错的地方：", hint=True)
    bullets(doc, [
        "IPv4 的 ihl 决定头长（可能带选项），不能假定 20 字节；",
        "IPv6 有扩展头链（逐跳/路由/目的选项/分片），必须走到 6/17/58 才是传输层；",
        "VLAN 可能多层（QinQ），要循环剥；",
        "以太网最小帧 60 字节，小包会被填充 0，**必须按 IP 头里的长度裁剪载荷**（见 5.7）。",
    ])
    h2(doc, "3.4  流追踪")
    body(doc, "用规范化五元组作为 key：把 (ip, port) 两端排序后再拼，这样 A→B 与 B→A 落到同一条流。"
              "方向由第一个纯 SYN 决定，之后同 key 的包都归入该流。流表用 LRU，超过 2 万条淘汰最久未用的。", hint=True)
    code(doc, "key = (proto, min((ip1,port1),(ip2,port2)), max((ip1,port1),(ip2,port2)))")
    h2(doc, "3.5  TCP 流重组")
    body(doc, "TCP 是字节流而非消息流：一个 HTTP 请求可能被拆成多个段，一个段也可能含多个请求。"
              "重组把碎片拼回连续字节，才能看到完整的应用层内容。", hint=True)
    bullets(doc, [
        "按 seq 定位写入偏移，比较时用 (seq-base) mod 2^32 取有符号值，处理序号回绕；",
        "重传用块合并去重，重叠部分保留先到的字节；",
        "允许空洞：只交付从起点连续的字节，中间缺一段就停住，避免拼出错误内容；",
        "每方向上限 512 KB，超出截断并标记。",
    ])
    slot(doc, "画一张重组示意图：三个报文段（seq 1000/2000/3000）拼成一条连续流")

    # 4 测试
    h1(doc, "4  测试与结果")
    h2(doc, "4.1  测试环境")
    table(doc,
          ["项", "值"],
          [["宿主机", "Windows 11 + VMware Workstation 17.6.1"],
           ["虚拟机", "Ubuntu 24.04.5 LTS Desktop，4 GB / 2 核"],
           ["网络", "VMnet1 仅主机网络 10.10.10.0/24；sniffer 10.10.10.10，victim 10.10.10.20"],
           ["依赖", "libpcap 1.10.4、Python 3.12、PyQt5"]],
          [3.0, 13.4])
    caption(doc, "表 5  测试环境")
    h2(doc, "4.2  功能测试")
    body(doc, "用脚本 scripts/selftest.py 跑了 14 项端到端检查，覆盖设备枚举、非法表达式、"
              "四种过滤、流聚合、应用层识别、进程归因、重组一致性、落盘回读。", hint=True)
    table(doc,
          ["#", "检查项", "结果"],
          [["1", "网卡枚举（9 块）", "通过"],
           ["2", "非法 BPF 表达式不崩溃且报错", "通过"],
           ["3", "实时抓包（108 包/3 秒）", "通过"],
           ["4", "统计可读（内核丢包 0）", "通过"],
           ["5", "过滤 icmp（17 包，全部为 ICMP）", "通过"],
           ["6", "过滤 tcp port 8080（114 包，全部命中）", "通过"],
           ["7", "过滤 host + 端口（and 组合，113 包）", "通过"],
           ["8", "过滤 TCP SYN（23 包，全部带 SYN）", "通过"],
           ["9", "流追踪聚合（14 条流）", "通过"],
           ["10", "应用层识别 HTTP（13 条）", "通过"],
           ["11", "进程归因（python3(4075)）", "通过"],
           ["12", "TCP 重组（请求行完整、长度对齐、无填充）", "通过"],
           ["13", "保存 pcap 并回读（125/125 包一致）", "通过"],
           ["14", "链路类型正确（LINKTYPE_ETHERNET）", "通过"]],
          [1.2, 11.4, 3.8])
    caption(doc, "表 6  端到端自测结果（14/14）")
    slot(doc, "贴一张 selftest.py 的输出截图")
    h2(doc, "4.3  重组正确性测试")
    body(doc, "对 5 条真实 HTTP 连接（每条下载 18 KB 文件）检查：请求行以 HTTP/1.1 结尾、"
              "Host 头只出现一次、请求头以空行结束、响应 200、正文长度与 Content-Length 一致。", hint=True)
    table(doc,
          ["检查项", "结果", "说明"],
          [["请求行完整", "5/5", "上行 103 字节，未被截断"],
           ["Host 头唯一", "5/5", "重传包没有被拼成重复内容"],
           ["请求头以空行结束", "5/5", "\\r\\n\\r\\n 边界正确"],
           ["响应 200", "5/5", "下行未串流"],
           ["正文长度对齐", "5/5", "18469/18469 字节，跨 3 个报文段"],
           ["合计", "25/25", "scripts/verify_reassembly.py"]],
          [4.6, 2.4, 9.4])
    caption(doc, "表 7  重组一致性检查")
    h2(doc, "4.4  第三方流量捕获")
    body(doc, "嗅探器作为第三方，抓取主机（10.10.10.1）与 victim（10.10.10.20）之间的会话，"
              "66 个包全部是“与自己无关”的流量，并可完整解析出 HTTP 请求与响应。", hint=True)
    code(doc, "10.10.10.1:65434 -> 10.10.10.20:8080  [SYN]\n"
              "10.10.10.20:8080 -> 10.10.10.1:65434  [SYN,ACK]\n"
              "10.10.10.1:65434 -> 10.10.10.20:8080  方法=GET URI=/README.md\n"
              "10.10.10.20:8080 -> 10.10.10.1:65434  状态=200 OK")
    h2(doc, "4.5  性能观察")
    body(doc, "小流量（<1 MB/s）下内核丢包为 0；两路 8080 会话并发时 CPU 占用约 10%（Python）。"
              "瓶颈在 Python 的逐包解析与界面渲染，而不在 libpcap。", hint=True)

    # 5 问题与解决
    h1(doc, "5  遇到的问题与解决")
    body(doc, "下面每一条都是实际踩到的坑，按“现象 → 根因 → 解决 → 启示”记录，"
              "其中 5.2、5.5、5.6 属于只有做到一定程度才会暴露的问题。", hint=True)

    h2(doc, "5.1  WSL2 抓不到别人的流量")
    body(doc, "现象：在 WSL2 里写抓包程序，只能看到 WSL 自己的流量。")
    body(doc, "根因：WSL2 是 NAT 后的独立虚拟机，虚拟网卡只收到发给它的帧，"
              "交换机不会把别人的单播转发过来。")
    body(doc, "解决：改用 VMware 虚拟机 + VMnet1 仅主机网络，嗅探机与 victim 同网段。")
    body(doc, "启示：抓包工具的上限由网络拓扑决定，代码写得再好也突破不了链路层。")

    h2(doc, "5.2  登录后黑屏")
    body(doc, "现象：装完 Ubuntu 能进登录界面，输入密码后整个屏幕变黑。")
    body(doc, "根因：建虚拟机时关闭了 3D 加速，同时禁用了 GL 渲染器；"
              "Ubuntu 24.04 的 GNOME Shell 需要 OpenGL 才能起会话。")
    body(doc, "解决：开启 3D；后来为稳定起见改为强制 Xorg 会话 + 软件渲染（Qt 侧设 QT_QPA_PLATFORM=xcb）。")

    h2(doc, "5.3  画面会“停住”不动")
    body(doc, "现象：桌面时钟几分钟不跳，鼠标点下去没反应，但机器还能 ping 通。")
    body(doc, "根因：在 Hyper-V 兼容模式下 SVGA3D 的帧缓冲会卡住，内核与网络仍在运行。")
    body(doc, "解决：关闭 3D 改用软件渲染；改变虚拟机窗口大小可强制重画一帧作为临时手段。")

    h2(doc, "5.4  进程归因为什么读不到 /proc")
    body(doc, "现象：流表里进程列一直是空。")
    body(doc, "排查：先做最小复现——自己开一对 socket，解析器能认出 python3(pid)，说明算法没问题；"
              "再看目标进程的 /proc/<pid>/fd，发现权限被拒。")
    body(doc, "根因：为了让程序免 sudo 抓包，给 python3 加了 cap_net_raw 能力；"
              "带文件能力的进程会被内核标记为不可 dump（dumpable=0），同用户的其他进程读不了它的 fd。")
    body(doc, "解决：进程归因需要 root 运行（root 有 CAP_SYS_PTRACE）。")
    body(doc, "启示：安全加固会改变可见性，抓包类工具要么要权限，要么功能打折。")

    h2(doc, "5.5  连接关闭后就查不到进程")
    body(doc, "现象：抓包结束后再统计，进程列全空。")
    body(doc, "根因：一个 curl 连接只活十几毫秒，收尾时 socket 早已从 /proc/net/tcp 消失。")
    body(doc, "解决：在流存活期间（收包时）就尝试解析，并把结果记在流对象上；解析器内部做快照缓存与限速。")

    h2(doc, "5.6  已建立的连接在 /proc 里 inode 为 0")
    body(doc, "现象：即使用 root、在连接活跃时查询，精确匹配仍然失败。")
    body(doc, "根因：该内核下已 accept 的连接在 /proc/net/tcp 中 inode 列为 0，只有监听套接字有真实 inode。")
    body(doc, "解决：加一条兜底——建立“监听端口 → 进程”映射，精确匹配失败时按端口归属判定。")
    body(doc, "启示：依赖系统接口的实现要多留一条降级路径。")

    h2(doc, "5.7  重组出来的 HTTP 请求尾部多出 6 个 \\x00")
    body(doc, "现象：界面上请求头后面显示一行方块（□□□□□□）。")
    body(doc, "排查：dump 载荷尾部，得到 ...Accept: */*\\r\\n\\r\\n\\x00\\x00\\x00\\x00\\x00\\x00，"
              "上行总长 103 字节而实际请求只有 97 字节。")
    body(doc, "根因：以太网最小帧 60 字节，短包尾部会填充 0；解析器把 TCP 头之后的字节全当载荷，"
              "把填充也算了进去。单包解析时看不出来，**做重组后才暴露**。")
    body(doc, "解决：按 IP 头里的长度字段裁剪——IPv4 用 total_len - ihl，IPv6 用 payload_len 减去扩展头；"
              "UDP 同理。补充单元测试防止回归。")
    slot(doc, "贴修复前后的对比截图（带方块 / 干净结尾）")

    h2(doc, "5.8  流内容面板每秒弹回顶部")
    body(doc, "现象：滚到中间读正文，一秒后视图跳回开头。")
    body(doc, "根因：流表每秒重建，重建后重新选中同一行，触发 selectionChanged → 文本重设 → 滚动条归零。")
    body(doc, "解决：记录当前显示的流 key，同一条流跳过重渲染；选中行未变化时不再调用 selectRow。")

    h2(doc, "5.9  pcap 尾部丢包")
    body(doc, "现象：抓包文件里最后一条流总是少几 KB，且 gap 检测为无空洞。")
    body(doc, "根因：测试用 `timeout` 发 SIGTERM 强杀进程，libpcap 的 dumper 缓冲未刷盘。")
    body(doc, "解决：改用 SIGINT（Ctrl-C）让程序走正常退出路径，由 pcap_dump_close 落盘。")

    h2(doc, "5.10  测试脚本自己写错了两处")
    body(doc, "现象：第一轮检查 5 项全 FAIL、响应状态行也 FAIL。")
    body(doc, "根因：检查脚本按 \\n 切分（HTTP 用 \\r\\n），且假设响应是 HTTP/1.1，"
              "而 Python 的 http.server 回的是 HTTP/1.0。")
    body(doc, "启示：断言要宽容于实现差异，先确认“是程序错还是测试错”。")

    # 6 分析
    h1(doc, "6  安全分析与思考")
    h2(doc, "6.1  抓包层次与分析层次")
    body(doc, "抓包发生在链路层（AF_PACKET），拿到的是“进协议栈之前”的原始帧；"
              "分析发生在用户态，按 OSI 逐层解封装。两者分离带来两个结果："
              "抓包可以做到与协议无关（什么都能抓），分析则必须有协议知识（能不能看懂）。", hint=True)
    h2(doc, "6.2  为什么 Thor 装了根证书就能解 HTTPS，却仍对某些内容无能为力")
    body(doc, "HTTPS 的可见性取决于“你在不在信任链上”。装了根证书 = 中间人可以签发被信任的证书，"
              "于是它能解密应用层；但传输层的行为（重传、窗口、拥塞控制）由内核维护，"
              "抓包工具只能观察不能改变，因此对“某些传输控制协议的内容”无能为力。"
              "本实验同理：重组能得到明文 HTTP，但对 TLS 只能得到密文块。", hint=True)
    h2(doc, "6.3  交换式网络与嗅探的边界")
    body(doc, "交换机按 MAC 表转发，第三方收不到别人的单播。本次能在 VMnet1 上抓到第三方流量，"
              "是因为虚拟交换机把帧泛洪给了同网段端口；在真实交换网络中需要端口镜像或 ARP 欺骗。", hint=True)
    h2(doc, "6.4  权限边界")
    body(doc, "抓包需要 CAP_NET_RAW；进程归因需要读别人的 /proc，实质需要 CAP_SYS_PTRACE。"
              "这也解释了为什么商用嗅探器通常以 root 或专用服务运行。", hint=True)

    # 7 不足
    h1(doc, "7  不足与改进方向")
    bullets(doc, [
        "只对 HTTP 做了应用层语义还原，DNS/TLS 仅做识别；要做通用分析需要按协议注册解析器；",
        "重组按方向缓存，未实现跨流的应用层消息边界（一个流里多个请求时是拼接显示）；",
        "Python 在高流量下会先成为瓶颈，可考虑 C++/Qt 重写，或用 PF_RING/TPACKET_V3 提升抓包路径；",
        "未实现 TLS 解密（需要中间人证书，属于另一类工作）；",
        "进程归因依赖 /proc 且有权限门槛，eBPF uprobe 可以做到更精确的归因。",
    ])

    # 8 参考
    h1(doc, "8  参考资料")
    bullets(doc, [
        "libpcap 官方仓库：https://github.com/the-tcpdump-group/libpcap",
        "pcap-filter 手册：man 7 pcap-filter",
        "Linux 收包路径：net/core/dev.c 的 netif_receive_skb",
        "TCP 可靠传输：RFC 793 / RFC 9293",
        "课件《软件与系统安全》实验 1A&1B 讲解（2026/11/10）",
    ], size=9.5)

    # 附录
    h1(doc, "附录 A  运行方式")
    code(doc, "git clone <仓库地址> && cd lab1a\n"
              "sudo apt install -y libpcap-dev python3-pyqt5\n\n"
              "# 单元测试（24 个，不需要 root）\n"
              "python3 -m unittest discover -s tests -t . -v\n\n"
              "# 命令行抓包 + 跟随流\n"
              "sudo python3 -m sniffer.cli -i enp0s18 -f \"tcp port 8080\" --flows --follow 1\n\n"
              "# 图形界面\n"
              "bash scripts/run-gui.sh\n\n"
              "# 端到端自测（14 项）\n"
              "sudo SNIFFER_IFACE=enp0s18 python3 scripts/selftest.py")

    h1(doc, "附录 B  AI 使用说明")
    body(doc, "按课程建议（p65），在此说明人机分工：", hint=True)
    table(doc,
          ["部分", "来源", "说明"],
          [["协议解析、重组算法", "本人设计 + AI 辅助查错", "分层结构、越界处理、seq 回绕由本人确定"],
           ["GUI 布局与样式", "AI 生成初稿", "本人调整列宽、刷新策略与交互"],
           ["环境搭建脚本", "AI 生成", "本人按实际环境修改并验证"],
           ["测试用例", "本人列出检查项，AI 补全代码", "断言标准由本人确定"]],
          [5.0, 5.4, 6.0])
    caption(doc, "表 8  人机分工")
    body(doc, "所有代码本人均能逐行解释；AI 生成部分已按实际抓包结果验证。", hint=True)

    doc.core_properties.title = "实验 1A 报告"
    doc.save(OUT)
    print("saved:", OUT)


if __name__ == "__main__":
    build()
