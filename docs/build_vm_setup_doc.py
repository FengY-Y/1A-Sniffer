"""生成《实验 1A 虚拟机配置手册》docx。

    python build_vm_setup_doc.py
输出：VMware虚拟机配置手册.docx（同目录）
"""
from __future__ import annotations

import os
import sys

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OUT_DOCX") or os.path.join(HERE, "VMware虚拟机配置手册.docx")
DIAGRAM = os.path.join(HERE, "topology.png")

BODY_FONT = "微软雅黑"
CODE_FONT = "Consolas"
ACCENT = RGBColor(0x1F, 0x38, 0x64)
GRAY = RGBColor(0x59, 0x59, 0x59)


# ---------------------------------------------------------------- 基础工具
def set_run_font(run, name=BODY_FONT, size=None, bold=None, color=None, eastasia=None):
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), name)
    rfonts.set(qn("w:hAnsi"), name)
    rfonts.set(qn("w:eastAsia"), eastasia or name)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color:
        run.font.color.rgb = color


def shade(paragraph_or_cell, fill):
    el = paragraph_or_cell._p if hasattr(paragraph_or_cell, "_p") else paragraph_or_cell._tc
    pr = el.get_or_add_pPr() if hasattr(el, "get_or_add_pPr") else el.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    pr.append(shd)


def body(doc, text, size=10.5, space_after=6, bold=False, color=None, indent=0):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.2
    if indent:
        p.paragraph_format.left_indent = Cm(indent)
    run = p.add_run(text)
    set_run_font(run, size=size, bold=bold, color=color)
    return p


def bullet(doc, text, size=10.5, level=0):
    p = doc.add_paragraph(style="List Bullet" if level == 0 else "List Bullet 2")
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.3
    run = p.add_run(text)
    set_run_font(run, size=size)
    return p


def step(doc, n, text, size=10.5):
    """手工编号，避免 Word 列表跨节续号（List Number 会一直往下数）。"""
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.left_indent = Cm(0.9)
    pf.first_line_indent = Cm(-0.7)
    pf.space_after = Pt(4)
    pf.line_spacing = 1.2
    run = p.add_run(f"{n}.  {text}")
    set_run_font(run, size=size)
    return p


def code(doc, text, size=9):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(3)
    pf.space_after = Pt(3)
    pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
    pf.left_indent = Cm(0.4)
    pf.right_indent = Cm(0.2)
    pf.keep_together = True
    shade(p, "F4F5F7")
    # 边框
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
        run = p.add_run(line)
        set_run_font(run, name=CODE_FONT, size=size, eastasia=BODY_FONT)
    return p


def h1(doc, text):
    p = doc.add_heading(level=1)
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run(text)
    set_run_font(run, size=15, bold=True, color=ACCENT)
    # 标题下细分隔线
    ppr = p._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "8")
    bottom.set(qn("w:color"), "C9D3E3")
    borders.append(bottom)
    ppr.append(borders)
    return p


def h2(doc, text):
    p = doc.add_heading(level=2)
    p.paragraph_format.space_before = Pt(9)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(text)
    set_run_font(run, size=11.5, bold=True, color=RGBColor(0x2E, 0x4A, 0x7A))
    return p


def table(doc, headers, rows, widths, header_fill="1F3864", font_size=9.5, zebra=True):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    # 单元格上下边距压到 0，行高就不会虚胖
    tblPr = t._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for side, val in (("top", 30), ("bottom", 30), ("left", 108), ("right", 108)):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    try:
        tblPr.insert_element_before(mar, "w:tblLook", "w:tblCaption", "w:tblDescription")
    except Exception:
        tblPr.append(mar)

    hdr = t.rows[0].cells
    for i, h in enumerate(headers):
        p = hdr[i].paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.line_spacing = 1.0
        run = p.add_run(h)
        set_run_font(run, size=font_size, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
        shade(hdr[i], header_fill)
    # 表头跨页重复
    # （放在最后统一处理，保证 trPr 内 cantSplit 在 tblHeader 之前）

    for r_i, row in enumerate(rows):
        cells = t.add_row().cells
        for i, val in enumerate(row):
            p = cells[i].paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.line_spacing = 1.0
            run = p.add_run(str(val))
            set_run_font(run, size=font_size)
            if zebra and r_i % 2 == 1:
                shade(cells[i], "F2F5FA")
    # 行内禁止跨页断开；表头跨页重复
    for idx, row in enumerate(t.rows):
        trPr = row._tr.get_or_add_trPr()
        trPr.append(OxmlElement("w:cantSplit"))
        if idx == 0:
            trPr.append(OxmlElement("w:tblHeader"))
        for i, w in enumerate(widths):
            row.cells[i].width = Cm(w)
    return t


def caption(doc, text, above=False):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(10 if above else 2)
    p.paragraph_format.space_after = Pt(2 if above else 8)
    # 表题在表上方，必须和表格同页
    p.paragraph_format.keep_with_next = bool(above)
    run = p.add_run(text)
    set_run_font(run, size=9, bold=above,
                 color=RGBColor(0x33, 0x33, 0x33) if above else GRAY)


# ---------------------------------------------------------------- 拓扑图
def draw_topology(path: str) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return False
    W, H = 1500, 640
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    try:
        f_big = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 26)
        f = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 23)
        f_small = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 19)
    except Exception:
        return False

    import math

    def dashed(x1, y1, x2, y2, color="#A6B1BD", width=3, steps=26):
        for i in range(0, steps, 2):
            ax = x1 + (x2 - x1) * i / steps
            ay = y1 + (y2 - y1) * i / steps
            bx = x1 + (x2 - x1) * (i + 1) / steps
            by = y1 + (y2 - y1) * (i + 1) / steps
            d.line([ax, ay, bx, by], fill=color, width=width)

    def arrow(x1, y1, x2, y2, color="#7f8c9b", width=3):
        d.line([x1, y1, x2, y2], fill=color, width=width)
        ang = math.atan2(y2 - y1, x2 - x1)
        for s in (-0.42, 0.42):
            d.line([x2, y2, x2 - 15 * math.cos(ang + s), y2 - 15 * math.sin(ang + s)],
                   fill=color, width=width)

    # ① NAT 云（画在最前面，虚线从交换机右侧接入）
    d.rounded_rectangle([1180, 190, 1470, 340], radius=16, fill="#F7F7F7", outline="#9AA4AE", width=3)
    d.multiline_text((1325, 240), "NAT (VMnet8)", font=f_big, fill="#333", anchor="mm")
    d.multiline_text((1325, 295), "每台 VM 的第二块网卡\n仅用于 apt / 上网", font=f_small,
                     fill="#555", anchor="mm", align="center", spacing=4)
    # NAT 是独立的网络，不画连线，避免误读

    # ③ 主机
    d.rounded_rectangle([60, 30, 390, 125], radius=10, fill="#EAF1FB", outline="#3B6EA5", width=3)
    d.multiline_text((225, 62), "Windows 主机", font=f, fill="black", anchor="mm")
    d.multiline_text((225, 97), "10.10.10.1 (VMnet1)", font=f_small, fill="#333", anchor="mm")
    arrow(225, 125, 225, 190)

    # ④ 虚拟交换机
    d.rounded_rectangle([60, 190, 1080, 268], radius=10, fill="#F3F6F9", outline="#8FA6BF", width=3)
    d.multiline_text((570, 229), "VMnet1 仅主机虚拟交换机    10.10.10.0/24",
                     font=f_big, fill="#33506e", anchor="mm")

    # ⑤ 三台 VM
    vms = [
        (70, "sniffer", "10.10.10.10", "Ubuntu Desktop\n抓包 + GUI", "#FFF4E0", "#C08A2E"),
        (395, "victim", "10.10.10.20", "Ubuntu Desktop\n被嗅探对象", "#EAF7EE", "#3F8F55"),
        (720, "server（可选）", "10.10.10.30", "Ubuntu Server\n对端 / 网关", "#F2EDF8", "#6C4C9E"),
    ]
    for x, name, ip, desc, fill, outline in vms:
        d.rounded_rectangle([x, 340, x + 280, 512], radius=10, fill=fill, outline=outline, width=3)
        d.text((x + 140, 366), name, font=f_big, fill="#222", anchor="mm")
        d.text((x + 140, 402), ip, font=f, fill="#333", anchor="mm")
        d.multiline_text((x + 140, 458), desc, font=f_small, fill="#444",
                         anchor="mm", align="center", spacing=4)
        arrow(x + 140, 268, x + 140, 340)

    d.text((60, 560), "实线：VMnet1 实验网段（抓包主战场）        NAT 是每台 VM 的另一块网卡，图中未连线",
           font=f_small, fill="#666")
    img.save(path)
    return True


# ---------------------------------------------------------------- 正文
def build():
    doc = Document()

    # 页面
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

    # 页脚页码
    footer_p = sec.footer.paragraphs[0]
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer_p.add_run("第 ")
    set_run_font(run, size=8.5, color=GRAY)
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    footer_p._p.append(fld)
    run2 = footer_p.add_run(" 页  ·  实验 1A 虚拟机配置手册")
    set_run_font(run2, size=8.5, color=GRAY)

    # 标题
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run("实验 1A  ·  虚拟机配置手册")
    set_run_font(run, size=24, bold=True, color=ACCENT)

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(14)
    run = p.add_run("VMware Workstation 17  +  Ubuntu 24.04 LTS Desktop  +  仅主机实验网段")
    set_run_font(run, size=10.5, color=GRAY)

    # 摘要框
    t = doc.add_table(rows=1, cols=1)
    t.style = "Table Grid"
    cell = t.rows[0].cells[0]
    shade(cell, "EEF3FA")
    cell.width = Cm(16.6)
    cell.text = ""
    lines = [
        ("这套配置要达到的目标", True),
        ("一台「嗅探机」能抓到同网段另外两台机器的流量，能随时打快照回滚，"
         "并且不影响你 Windows 主机的正常上网。", False),
        ("本机现状：VMware 17.6.1（D:\\soft_computer\\VMware Workstation）；"
         "VMnet1 已是 10.10.10.0/24，主机 10.10.10.1；C 盘剩余 50 GB、D 盘剩余 99.6 GB；"
         "Hyper-V 仍在运行（需处理）。", False),
    ]
    for i, (text, bold) in enumerate(lines):
        p = cell.paragraphs[0] if i == 0 else cell.add_paragraph()
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.line_spacing = 1.3
        run = p.add_run(text)
        set_run_font(run, size=10.5 if bold else 9.5, bold=bold,
                     color=ACCENT if bold else None)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)

    # 一、规划
    h1(doc, "一、先规划：三台机器、两块网卡")
    body(doc, "整个实验只需要一个私有网段 10.10.10.0/24（VMware 的 VMnet1，仅主机模式）。"
              "每台虚拟机再挂一块 NAT 网卡专门用来 apt 装依赖，抓包时不看它。")
    if os.path.exists(DIAGRAM):
        doc.add_picture(DIAGRAM, width=Cm(16.2))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        caption(doc, "图 1  实验网络拓扑")

    caption(doc, "表 1  设备与地址规划", above=True)
    table(doc,
          ["设备", "角色", "VMnet1 地址", "说明"],
          [["Windows 主机", "第三台机器 / 流量源", "10.10.10.1", "VMware 自动创建，可直接 ping 虚拟机"],
           ["sniffer", "嗅探机（实验主体）", "10.10.10.10", "Ubuntu Desktop，跑抓包程序与 GUI"],
           ["victim", "被嗅探对象", "10.10.10.20", "Ubuntu Desktop，由 sniffer 克隆而来"],
           ["server（可选）", "对端 / 网关", "10.10.10.30", "只为演示「抓到第三方流量」时使用"]],
          [3.0, 4.2, 3.4, 6.0])

    body(doc, "为什么用「仅主机」而不是「桥接」：校园网常开客户端隔离，桥接后虚拟机之间可能根本 ping 不通；"
              "仅主机网络完全在你自己机器内部，不依赖任何外部网络，答辩演示也不会翻车。", size=9.5, color=GRAY)

    # 二、前置
    h1(doc, "二、前置检查（10 分钟）")
    h2(doc, "2.1  Hyper-V 是否抢占（你当前就是这种情况）")
    body(doc, "Windows 上只要 Hyper-V 平台在运行（WSL2、Docker Desktop、内核隔离都会触发），"
              "VMware 就会退到兼容模式：能用，但明显变卡，录屏时一眼能看出来。先确认再决定。")
    code(doc, "Get-Service HvHost, vmcompute | Select-Object Name, Status\n"
              "bcdedit /enum \"{current}\" | Select-String hypervisorlaunchtype")
    body(doc, "两个服务都是 Running、或显示 hypervisorlaunchtype Auto，就说明被占用了。按下面三选一处理：")
    caption(doc, "表 2  Hyper-V 的三种处理方式", above=True)
    table(doc,
          ["选择", "操作", "代价"],
          [["A. 关内核隔离（建议先试）", "Windows 安全中心 → 设备安全性 → 内核隔离 → 内存完整性：关 → 重启", "基本无感"],
           ["B. 做实验期间关掉 Hyper-V", "wsl --shutdown  →  bcdedit /set hypervisorlaunchtype off  →  重启",
            "WSL2 / Docker 暂时不能用；恢复命令：bcdedit /set hypervisorlaunchtype auto"],
           ["C. 不处理", "直接往下做", "慢，但功能不缺"]],
          [4.6, 7.4, 4.6])
    body(doc, "处理完在「任务管理器 → 性能 → CPU」右下角应看到「虚拟化：已启用」。", size=9.5, color=GRAY)

    h2(doc, "2.2  确认版本与资源")
    caption(doc, "表 3  前置条件", above=True)
    table(doc,
          ["检查项", "方法", "期望"],
          [["VMware 版本", "帮助 → 关于", "17.x（你的是 17.6.1，个人使用免费）"],
           ["虚拟化", "任务管理器 → 性能 → CPU", "虚拟化：已启用"],
           ["磁盘", "资源管理器", "C 盘 50 GB、D 盘 99.6 GB 可用（虚拟机放 D 盘）"],
           ["Ubuntu ISO", "镜像站下载", "24.04.5.1 Desktop，5.82 GB"]],
          [3.2, 7.0, 6.4])
    body(doc, "ISO 下载（清华镜像，24.04.x 目录下的 desktop-amd64.iso）：")
    code(doc, "https://mirrors.tuna.tsinghua.edu.cn/ubuntu-releases/24.04/")

    # 三、网络
    h1(doc, "三、核对虚拟网络（本机已配好）")
    body(doc, "这台机器上 VMnet1 已经是 10.10.10.0/24、主机适配器 10.10.10.1，不改也能用。"
              "下面只是核对，三处对得上就直接跳到第四章。")
    caption(doc, "表 4  VMnet1 核对项", above=True)
    table(doc,
          ["核对项", "在哪看", "期望值"],
          [["VMnet1 子网", "编辑 → 虚拟网络编辑器（需管理员）", "10.10.10.0 / 255.255.255.0"],
           ["主机适配器", "Windows「网络连接」里的 VMware Network Adapter VMnet1", "10.10.10.1"],
           ["DHCP 范围", "虚拟网络编辑器 → VMnet1 → DHCP 设置", "10.10.10.128 – 10.10.10.254"],
           ["VMnet8（NAT）", "不用管", "保持默认 192.168.142.0/24"]],
          [3.4, 8.4, 4.8])
    body(doc, "对不上才需要改：虚拟网络编辑器里选中 VMnet1，把子网 IP 改成 10.10.10.0、掩码 255.255.255.0，"
              "勾选「将主机虚拟适配器连接到此网络」，点应用。", size=9.5, color=GRAY)
    body(doc, "这块 10.10.10.1 的主机适配器可以直接当第三台机器：从 Windows 就能 ping 虚拟机、给它发流量，"
              "演示「抓到第三方流量」时不用再开第三台虚拟机。", size=9.5, color=GRAY)

    # 四、建 VM
    h1(doc, "四、创建 sniffer 虚拟机")
    h2(doc, "4.1  新建向导")
    step(doc, 1, "「文件 → 新建虚拟机」→ 选择「典型」→ 下一步。")
    step(doc, 2, "选择「稍后安装操作系统」——先建空机再挂 ISO，避免「简易安装」擅自改配置。")
    step(doc, 3, "客户机操作系统：Linux；版本选「其他 Linux 6.x 内核 64 位」。\n"
                  "（你的列表里没有 Ubuntu，这是正常的：下拉可滚动，Ubuntu 在 U 段；"
                  "实在找不到就用「其他 Linux 6.x 内核 64 位」，只影响默认硬件，不影响抓包。）")
    step(doc, 4, "虚拟机名称 sniffer，位置选 D:\\soft_computer\\VMs\\sniffer（不要有中文和空格）。")
    step(doc, 5, "磁盘大小 25 GB，选择「将虚拟磁盘拆分成多个文件」。")

    h2(doc, "4.2  自定义硬件（关键）")
    caption(doc, "表 5  虚拟机硬件参数", above=True)
    table(doc,
          ["项目", "取值", "原因"],
          [["内存", "4096 MB", "Ubuntu 桌面流畅运行；宿主 16 GB 可给 6144"],
           ["处理器", "2 核", "抓包线程 + 界面线程各占一个"],
           ["虚拟化 Intel VT-x/EPT", "不勾选", "那是嵌套虚拟化用的，本实验不需要"],
           ["显示器 · 加速 3D 图形", "取消勾选", "Qt 界面在软件渲染下更稳，避免花屏/黑屏"],
           ["声卡 / 打印机", "移除", "减少启动告警，省资源"],
           ["网络适配器 1", "NAT", "只用来 apt、查资料"],
           ["网络适配器 2", "自定义 → VMnet1", "实验网段，抓包主战场"]],
          [5.0, 4.6, 7.0])

    h2(doc, "4.3  挂载 ISO 并安装")
    step(doc, 1, "虚拟机设置 → CD/DVD → 使用 ISO 映像文件 → 选中下载好的 ubuntu-24.04.x-desktop-amd64.iso。")
    step(doc, 2, "启动虚拟机，安装语言选「中文（简体）」或 English 均可。")
    step(doc, 3, "安装类型选「交互式安装」；软件选择「最小安装」，不勾「安装第三方驱动」。")
    step(doc, 4, "磁盘：选「清除整个磁盘并安装 Ubuntu」（这是虚拟磁盘，不会影响你的实体机）。")
    step(doc, 5, "用户名用小写英文（如 lab），密码记牢 —— 后面 sudo 会一直用。")
    step(doc, 6, "时区选 Shanghai，安装完成后重启，并在虚拟机设置里把 CD/DVD 改为「使用物理驱动器」以免重复挂载。")

    # 五、装完配置
    h1(doc, "五、装完后的十分钟配置")
    h2(doc, "5.1  基础软件")
    code(doc, "sudo apt update\n"
              "sudo apt install -y build-essential git cmake libpcap-dev tcpdump python3-pyqt5\n"
              "sudo systemctl enable --now open-vm-tools")
    body(doc, "open-vm-tools 负责剪贴板共享、拖拽、分辨率自适应；不装的话这两项都会失效。")

    h2(doc, "5.2  认网卡、配静态 IP")
    code(doc, "ip -br a          # 一般 ens33 = NAT，ens37 = VMnet1\n"
              "nmcli con show    # 第二块网卡通常叫 \"Wired connection 2\"\n\n"
              "sudo nmcli con mod \"Wired connection 2\" ipv4.method manual ipv4.addresses 10.10.10.10/24\n"
              "sudo nmcli con up \"Wired connection 2\"\n\n"
              "ping -c 2 10.10.10.1     # 能通到 Windows 主机就对了")
    body(doc, "如果网卡名不是 ens37，用 ip -br a 的输出替换即可；连接名以 nmcli con show 为准。", size=9.5, color=GRAY)

    h2(doc, "5.3  免 sudo 抓包（可选）")
    code(doc, "sudo setcap cap_net_raw,cap_net_admin=eip $(readlink -f $(which python3))")
    body(doc, "加了能力之后 GUI 可以直接启动，不用 sudo 跑图形程序。注意：这等于让本机所有 Python 脚本都能抓包，"
              "仅在实验虚拟机里这么做。", size=9.5, color=GRAY)

    h2(doc, "5.4  装实验代码并跑一遍")
    code(doc, "git clone <你的仓库地址>  ~/lab1a     # 或把 lab1a 目录拷进来\n"
              "cd ~/lab1a\n"
              "python3 -m unittest discover -s tests -t . -v     # 12 个用例应全绿\n"
              "python3 -m sniffer.cli -r demo/demo.pcap --flows   # 离线解析 14 个包")

    # 六、克隆
    h1(doc, "六、克隆出 victim（不要重装）")
    step(doc, 1, "先关机（不是挂起）。右键 sniffer → 管理 → 克隆。")
    step(doc, 2, "选择「虚拟机中的当前状态」→「创建完整克隆」（不要链接克隆，父机删了子机就废）。")
    step(doc, 3, "名称 victim，位置 D:\\soft_computer\\VMs\\victim。")
    step(doc, 4, "启动 victim，改三样，避免主机名、machine-id、IP 冲突：")
    code(doc, "sudo hostnamectl set-hostname victim\n"
              "sudo truncate -s 0 /etc/machine-id && sudo systemd-machine-id-setup\n"
              "sudo nmcli con mod \"Wired connection 2\" ipv4.addresses 10.10.10.20/24\n"
              "sudo nmcli con up \"Wired connection 2\"")
    body(doc, "需要第三台 server 时同样克隆，地址改 10.10.10.30。")

    # 七、验证
    h1(doc, "七、验收：五条命令确认环境可用")
    caption(doc, "表 6  环境验收清单", above=True)
    table(doc,
          ["#", "在哪台机器执行", "命令", "通过标准"],
          [["1", "victim", "ping -c 3 10.10.10.10", "通，丢包 0"],
           ["2", "sniffer", "sudo tcpdump -i ens37 -n icmp", "victim ping 时能看到请求与应答"],
           ["3", "sniffer", "ip link show ens37", "输出里有 PROMISC 标志"],
           ["4", "sniffer", "sudo python3 -m sniffer.cli -i ens37", "列表滚动，能看到 TCP/UDP/ICMP"],
           ["5", "Windows 主机", "ping 10.10.10.10", "通（说明 VMnet1 主机适配器正常）"]],
          [0.9, 3.4, 6.2, 6.1])

    body(doc, "第 2 条如果「抓不到 victim 与第三台机器之间的单播流量」，这是交换式网络的正常行为，"
              "不是配置错误：交换机会按 MAC 表转发，不会把别人的单播帧送给你。要演示这一点，用 ARP 欺骗，"
              "包会主动发到你的 MAC 上，此时不需要混杂模式。", size=9.5)

    # 八、快照
    h1(doc, "八、快照策略")
    caption(doc, "表 7  建议保留的快照", above=True)
    table(doc,
          ["时机", "名称", "用途"],
          [["装完系统、配好 IP", "01-clean", "出问题回到起点"],
           ["装完依赖与代码", "02-deps", "重装系统也不用重配"],
           ["演示前", "03-demo", "录视频时的干净状态"]],
          [6.2, 3.6, 6.4])
    body(doc, "快照会持续占用磁盘（每个 1–3 GB），做完实验后把旧快照删除或「整合」，"
              "D 盘只剩 55 GB，别让它堆满。")

    # 九、故障
    h1(doc, "九、常见故障速查")
    caption(doc, "表 8  故障排查", above=True)
    table(doc,
          ["现象", "原因", "处理"],
          [["启动时提示此平台不支持虚拟化 / 极慢", "Hyper-V 占用", "见第二章，关内核隔离或关 Hyper-V"],
           ["开机黑屏、画面撕裂", "3D 加速与驱动不兼容", "虚拟机设置里取消「加速 3D 图形」"],
           ["安装时找不到磁盘", "客户机类型选了 CentOS 等老预设", "改「其他 Linux 6.x 内核 64 位」或把磁盘类型改为 SCSI"],
           ["ping 不通 victim", "两块网卡接反 / 防火墙", "ip -br a 确认 10.10.10.x 在哪块网卡；sudo ufw status"],
           ["tcpdump 没有任何输出", "网卡名写错或选了 NAT 那块", "tcpdump -D 列出可用网卡"],
           ["复制粘贴、分辨率自适应失效", "open-vm-tools 未装", "sudo apt install open-vm-tools-desktop 后重启"],
           ["挂起再恢复后时间不准", "时钟漂移", "安装 open-vm-tools 并 systemctl restart open-vm-tools"],
           ["磁盘空间快速减少", "快照堆积", "虚拟机 → 快照管理器，删除旧快照"]],
          [5.6, 4.8, 6.2])

    # 附录
    h1(doc, "附录 A  参数速查")
    caption(doc, "表 9  配置速查", above=True)
    table(doc,
          ["项目", "值"],
          [["VMware 版本", "17.6.1（D:\\soft_computer\\VMware Workstation）"],
           ["虚拟机存放", "D:\\soft_computer\\VMs\\"],
           ["客户机类型", "其他 Linux 6.x 内核 64 位"],
           ["CPU / 内存 / 磁盘", "2 核 / 4096 MB / 25 GB（拆分多文件）"],
           ["网卡", "NAT（ens33） + 自定义 VMnet1（ens37）"],
           ["VMnet1 子网", "10.10.10.0/24，主机 10.10.10.1"],
           ["sniffer / victim / server", "10.10.10.10 / 10.10.10.20 / 10.10.10.30"],
           ["显示", "关闭 3D 加速"],
           ["系统", "Ubuntu 24.04 LTS Desktop，最小安装"]],
          [4.6, 11.6])

    h1(doc, "附录 B  命令速查")
    code(doc, "# 装依赖\n"
              "sudo apt update && sudo apt install -y build-essential git cmake libpcap-dev tcpdump python3-pyqt5\n\n"
              "# 配静态 IP\n"
              "sudo nmcli con mod \"Wired connection 2\" ipv4.method manual ipv4.addresses 10.10.10.10/24\n"
              "sudo nmcli con up \"Wired connection 2\"\n\n"
              "# 免 sudo 抓包\n"
              "sudo setcap cap_net_raw,cap_net_admin=eip $(readlink -f $(which python3))\n\n"
              "# 冒烟测试\n"
              "sudo tcpdump -i ens37 -n -c 5\n"
              "python3 -m sniffer.cli -i ens37 -f \"tcp port 80\"\n\n"
              "# 改主机名 / machine-id（克隆后）\n"
              "sudo hostnamectl set-hostname victim\n"
              "sudo truncate -s 0 /etc/machine-id && sudo systemd-machine-id-setup")

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(16)
    run = p.add_run("配套材料：实验 1A 实施方案（环境选择、七天排期、报告与视频模板）、lab1a 源码骨架。")
    set_run_font(run, size=9, color=GRAY)

    doc.core_properties.title = "实验 1A 虚拟机配置手册"
    doc.core_properties.author = "lab1a"
    doc.save(OUT)
    print("saved:", OUT)
    return OUT


if __name__ == "__main__":
    os.makedirs(HERE, exist_ok=True)
    ok = draw_topology(DIAGRAM)
    print("diagram:", ok)
    build()
