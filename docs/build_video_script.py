"""生成《实验 1A 演示视频脚本》docx。

    python build_video_script.py

内容：要求解读 → 录制前准备 → 6 个镜头的分镜与逐字解说词 →
录制方案 → 合成 → 提交检查清单 → 常见问题。
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from docx import Document                                    # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH                 # noqa: E402
from docx.oxml import OxmlElement                             # noqa: E402
from docx.oxml.ns import qn                                   # noqa: E402
from docx.shared import Cm, Pt, RGBColor                      # noqa: E402

import build_report_skeleton as R                             # noqa: E402

OUT = os.path.join(HERE, "实验1A-演示视频脚本.docx")


def narrate(doc, text):
    """解说词块：浅蓝底、左侧粗竖线、正文字号稍大，方便照着念。"""
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.left_indent = Cm(0.5)
    pf.space_before = Pt(4)
    pf.space_after = Pt(8)
    pf.line_spacing = 1.45
    R.shade(p, "EEF3FA")
    ppr = p._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), "18")
    left.set(qn("w:space"), "8")
    left.set(qn("w:color"), "3B6EA5")
    borders.append(left)
    ppr.append(borders)
    R.set_run(p.add_run("解说词："), size=9, bold=True, color=RGBColor(0x2E, 0x4A, 0x7A))
    R.set_run(p.add_run(text), size=11)
    return p


def shot(doc, title, time_range, screen, actions, words):
    R.h2(doc, f"{title}（{time_range}）")
    R.body(doc, f"画面：{screen}", size=10)
    if actions:
        R.body(doc, "操作：", size=10)
        for a in actions:
            R.bullets(doc, [a], size=10)
    narrate(doc, words)


def build():
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.top_margin = Cm(2.2)
    sec.bottom_margin = Cm(2.0)
    sec.left_margin = Cm(2.2)
    sec.right_margin = Cm(2.2)

    normal = doc.styles["Normal"]
    normal.font.name = R.BODY_FONT
    normal.font.size = Pt(10.5)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), R.BODY_FONT)

    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    R.set_run(fp.add_run("实验 1A 演示视频脚本 · 第 "), size=8.5, color=R.GRAY)
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    fp._p.append(fld)
    R.set_run(fp.add_run(" 页"), size=8.5, color=R.GRAY)

    # 标题
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    R.set_run(p.add_run("实验 1A  演示视频脚本"), size=22, bold=True, color=R.ACCENT)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(12)
    R.set_run(p.add_run("5 分钟 · 6 个镜头 · 逐字解说"), size=11, color=R.GRAY)

    # 一、要求
    R.h1(doc, "一、课件对视频的要求")
    body = R.body
    body(doc, "课件 p3 与 p33 的要求原文是：用其他 OS 开发的同学，需要提供“编译成功、运行成功”的视频，"
              "并且要展示“程序编译、部署、测试的全过程”。判卷机是 Windows，所以这段视频是评分的必要材料，不是可选项。", hint=True)
    R.table(doc,
            ["要求", "落到视频里就是"],
            [["编译成功", "Python 没有编译步骤，用“安装依赖 + 启动程序不报错”代替；"
                          "如果愿意，可以额外用 cpp/mini_sniff.c 编译一次 C 版本作为补充"],
             ["运行成功", "界面正常打开、能抓到包、能点开详情"],
             ["部署过程", "从干净状态装依赖，或至少展示依赖检查"],
             ["测试过程", "跑单元测试（24 个用例）与端到端自测（14 项）"],
             ["解说", "每一步说清楚“在做什么、为什么这么做、结果说明什么”"],
             ["时长", "建议 3–5 分钟；超过 6 分钟容易让评阅人失去耐心"],
             ["命名", "张三_202618008829001_ex1A_play.mp4"]],
            [4.0, 12.4])
    R.caption(doc, "表  视频要求对照")

    # 二、准备
    R.h1(doc, "二、录制前 30 分钟准备")
    R.h2(doc, "2.1  环境检查")
    R.table(doc,
            ["检查项", "做法", "通过标准"],
            [["虚拟机状态", "sniffer 开机，victim 开机（用于第三方流量演示）", "两机都能 ping 通"],
             ["HTTP 服务", "在 sniffer 上跑 python3 -m http.server 8080 --bind 10.10.10.10", "浏览器能打开 8080"],
             ["界面", "bash scripts/run-gui.sh 能正常打开", "三栏布局正常显示"],
             ["测试", "python3 -m unittest discover -s tests -t . -v", "24 个用例全绿"],
             ["字体", "终端字号调到 14–16 号", "录屏里能看清命令"],
             ["桌面", "关掉无关窗口、清空桌面图标、关闭通知", "画面干净"]],
            [3.0, 9.0, 4.4])
    R.caption(doc, "表  录制前检查")

    R.h2(doc, "2.2  一次性准备命令")
    R.code(doc, "cd ~/lab1a\n"
                "# 1) 起一个 HTTP 服务当被访问对象\n"
                "nohup python3 -m http.server 8080 --bind 10.10.10.10 > /tmp/http.log 2>&1 &\n\n"
                "# 2) 确认端口通了\n"
                "curl -s -o /dev/null -w '%{http_code}\\n' http://10.10.10.10:8080/README.md\n\n"
                "# 3) 清屏、放大字体（终端里按 Ctrl+Shift++ 也行）\n"
                "clear && printf '\\e[8;40;120t'")

    R.h2(doc, "2.3  录制工具怎么选")
    R.table(doc,
            ["方案", "适合", "优点", "缺点"],
            [["OBS Studio", "想一次录完", "画面+声音同时录，不用后期", "要先装：sudo apt install obs-studio"],
             ["GNOME 自带录屏", "分段录", "零安装，Ctrl+Alt+Shift+R 开始/结束", "**不录声音**，要后期合成"],
             ["手机拍屏幕", "兜底", "不用装任何东西", "画质差，显得不专业"]],
            [3.4, 2.6, 5.4, 5.0])
    R.caption(doc, "表  录制方案")
    R.body(doc, "推荐：**OBS 一次成型**。装好后设两个来源——“屏幕捕获”和“音频输入”，"
                "录完直接是 mp4，省掉合成步骤。如果 OBS 装不上，就用 GNOME 录屏分段录，再用 ffmpeg 把声音合进去。", hint=True)

    # 三、分镜
    R.h1(doc, "三、分镜与解说词")
    R.body(doc, "总长约 5 分钟。每段都可以单独重录，出错了只重录这一段。", hint=True)

    shot(doc, "镜头 1  开场", "0:00–0:20",
         "桌面 + 终端窗口（还没开始操作）",
         ["鼠标停在终端上，不要动", "语速放慢，先报姓名学号"],
         "老师好，我是×××，学号××××。这是我实验 1A 的演示：一个带图形界面的网络嗅探器。"
         "整个演示大概五分钟，我会依次展示环境与部署、抓包、协议过滤、协议解析、流追踪，"
         "最后演示这次重点做的 TCP 流重组。")

    shot(doc, "镜头 2  环境与部署", "0:20–1:00",
         "终端：显示 uname -a、ip -br a、目录结构，然后跑单元测试",
         ["输入 uname -a 和 ip -br a，让观众看到两块网卡",
          "输入 ls sniffer/ 展示模块",
          "跑单元测试，等结果全部 OK"],
         "实验环境是一台 Ubuntu 24.04 虚拟机，两块网卡：一块 NAT 用来上网装依赖，"
         "一块 VMnet1 是实验网段，地址 10.10.10.10。代码分五层：pcap 是 libpcap 的绑定，"
         "decode 做逐层解析，flows 做流表和进程归因，reassembly 做 TCP 重组，"
         "上面是命令行和图形两套界面。因为是 Python，没有编译步骤，部署就是装依赖；"
         "装完先跑单元测试，二十四个用例，覆盖解析、重组、pcap 读写，全部通过。"
         "这一步不需要 root，也不需要网卡，能先保证核心逻辑是对的。")

    shot(doc, "镜头 3  抓包", "1:00–1:40",
         "GUI 窗口：网卡下拉 → 开始 → 列表滚动 → 点开始制造流量",
         ["点「开始」，等列表滚动",
          "另开终端（或从主机）ping 与 curl，制造流量",
          "回到界面，让列表再滚一会儿"],
         "现在打开界面。网卡默认选中的是 enp0s18，也就是实验网段那块，这是程序自己按地址段挑的。"
         "点开始，列表开始滚动。我从另一台机器访问这台机器的 8080 端口，"
         "可以看到三次握手、HTTP 请求和响应都在列表里，协议列按类型着色。")

    shot(doc, "镜头 4  协议过滤", "1:40–2:15",
         "过滤框：icmp → tcp port 8080 → host 与端口组合",
         ["输入 icmp 回车，稍停两秒让观众看清只剩 ICMP",
          "改成 tcp port 8080 回车",
          "再改成 host 10.10.10.1 and tcp port 8080 回车"],
         "过滤走的是 BPF 表达式，编译之后装进内核，不匹配的包在进入用户态之前就被丢掉了，"
         "所以流量大也不会拖慢界面。输入 icmp，列表只剩 ping 的请求和应答；"
         "改成 tcp port 8080，只剩 HTTP；也可以写 host 加端口这样的与运算。")

    shot(doc, "镜头 5  协议解析", "2:15–2:45",
         "点一个 HTTP 包：下方协议树 + 右侧十六进制",
         ["点一条 HTTP 的包",
          "鼠标在协议树上从上往下划，停在应用层",
          "鼠标划一下右侧十六进制里的明文请求行"],
         "点一个 HTTP 包。下面是协议树，从以太网、IP、TCP 一直解析到应用层，"
         "能直接看到请求方法、URI 和 Host。右边是原始字节，HTTP 是明文，所以能直接看到请求行。"
         "这就是抓包层次和分析层次的区别：抓包在链路层拿到原始帧，解析在用户态逐层还原。")

    shot(doc, "镜头 6  流追踪与进程归因", "2:45–3:15",
         "切到「流追踪」页：一条流、进程列",
         ["点「流追踪」标签",
          "点一条 HTTP 流，让下方显示内容",
          "鼠标指一下「进程」列"],
         "切到流追踪页。同一条连接的双向报文被合并成一条流，显示包数、字节数、连接状态，"
         "还有归属进程。进程这一列是按 /proc 里的 socket inode 反查出来的，"
         "需要 root 权限才能看到别的进程。")

    shot(doc, "镜头 7  TCP 流重组（重点）", "3:15–4:00",
         "同一页下方：完整的 HTTP 请求与响应，向下滚动展示正文",
         ["选中一条 8080 的流",
          "鼠标在下方文本区缓慢向下滚动，露出请求头与响应头",
          "停在 Content-Length 与正文处"],
         "这是这次重点做的部分：TCP 流重组。TCP 提供的是字节流，不是消息流，"
         "一个 HTTP 响应会被拆成好几个报文段，逐包看只能看到碎片。"
         "下面这块是把三个报文段按序号拼回去的结果：请求行完整，响应头和正文都在，"
         "正文长度和 Content-Length 完全一致。重组还顺带发现了一个 bug——"
         "以太网最小帧填充的零被当成载荷，单包看是看不出来的。")

    shot(doc, "镜头 8  抓第三方流量", "4:00–4:30",
         "victim 虚拟机窗口 + 嗅探器同时抓包",
         ["在 victim 上访问主机，或从主机访问 victim",
          "回到嗅探器，展示列表里出现的是别人的会话"],
         "最后演示抓别人的流量。左边是另一台虚拟机，它和主机之间的会话，"
         "嗅探器既不发送也不接收，只是旁观，同样能抓到，并且能完整解析出 HTTP 内容。"
         "这说明混杂模式下，虚拟交换机把帧也转发给了嗅探器。")

    shot(doc, "镜头 9  收尾", "4:30–5:00",
         "回到终端或界面首页",
         ["停掉抓包", "鼠标回到窗口中间，静止"],
         "不足的地方：目前只对 HTTP 做了应用层还原，DNS 和 TLS 只做到识别；"
         "高流量下 Python 会成为瓶颈，后续可以用 C++ 重写，或者用 eBPF 做更精确的进程归因。"
         "以上就是全部演示，谢谢老师。")

    # 四、操作速查
    R.h1(doc, "四、录制时用的命令速查")
    R.code(doc, "# 终端 A：单元测试（镜头 2）\n"
                "cd ~/lab1a && python3 -m unittest discover -s tests -t . -v\n\n"
                "# 终端 B：制造流量（镜头 3 之后一直可用）\n"
                "bash ~/lab1a/scripts/demo_traffic.sh 120\n\n"
                "# 主机侧也可以制造（Windows PowerShell）\n"
                "curl.exe -s -o NUL http://10.10.10.10:8080/README.md\n\n"
                "# 端到端自测（想展示更完整，可放在镜头 2 之后）\n"
                "sudo SNIFFER_IFACE=enp0s18 python3 scripts/selftest.py")

    # 五、合成
    R.h1(doc, "五、录完之后：合成与压缩")
    R.h2(doc, "5.1  如果用了 GNOME 录屏（无声音）")
    R.body(doc, "GNOME 录屏保存为 webm 且不含声音。用手机或耳机单独录一段解说，再用 ffmpeg 合起来：", hint=True)
    R.code(doc, "# 1) 把 webm 转成 mp4\n"
                "ffmpeg -i ~/Videos/Screencast*.webm -r 30 -c:v libx264 -crf 23 screen.mp4\n\n"
                "# 2) 把录音和画面合并（-shortest 以短的那个为准）\n"
                "ffmpeg -i screen.mp4 -i voice.m4a -c:v copy -c:a aac -shortest play.mp4")
    R.h2(doc, "5.2  如果用了 OBS")
    R.body(doc, "录完直接就是 mp4，只需要压缩体积（课件没限大小，但 200 MB 以内比较稳妥）：", hint=True)
    R.code(doc, "ffmpeg -i raw.mp4 -c:v libx264 -crf 26 -preset medium -c:a aac -b:a 128k out.mp4")
    R.h2(doc, "5.3  分段录制的拼接")
    R.code(doc, "# 把多个片段按顺序拼成一个\n"
                "printf \"file 'p1.mp4'\\nfile 'p2.mp4'\\nfile 'p3.mp4'\\n\" > list.txt\n"
                "ffmpeg -f concat -safe 0 -i list.txt -c copy play.mp4")

    # 六、清单
    R.h1(doc, "六、提交前检查清单")
    R.table(doc,
            ["项", "确认内容"],
            [["□ 命名", "张三_202618008829001_ex1A_play.mp4（换成自己的姓名学号）"],
             ["□ 时长", "3–5 分钟，最长不超过 6 分钟"],
             ["□ 有解说", "全程有声音，能听清；不是只有背景音乐"],
             ["□ 有部署/测试", "镜头 2 里能看到装依赖或跑测试的过程"],
             ["□ 有编译", "Python 无编译，建议额外编译一次 cpp/mini_sniff.c 作为补充"],
             ["□ 画面可读", "终端字号够大，录屏分辨率 1280×720 以上"],
             ["□ 无隐私", "没有聊天窗口、没有其他课程材料、没有个人信息泄露"],
             ["□ 能播放", "用另一台电脑播放一次，确认没有黑屏/无声"],
             ["□ 大小", "200 MB 以内"]],
            [3.4, 13.0])
    R.caption(doc, "表  提交前逐项确认")

    # 七、常见问题
    R.h1(doc, "七、常见问题")
    R.table(doc,
            ["问题", "处理"],
            [["录到一半界面卡住", "虚拟机是软件渲染，别同时跑两个大程序；录制前关掉浏览器"],
             ["声音太小或有回声", "用耳机麦克风，OBS 里把麦克风增益调到 -6dB 左右"],
             ["鼠标乱飞看不清", "刻意放慢，说到哪个区域就把鼠标停在那里两秒"],
             ["讲太快", "每段按秒表练两遍，语速大约每秒 4–5 个字"],
             ["忘了下一步说什么", "把这份脚本打印出来放屏幕旁边，照着念，不要背"],
             ["文件太大", "用 5.2 的 ffmpeg 命令压到 720p"],
             ["录完发现漏了重组", "只重录镜头 7，最后用 5.3 的命令拼进去"]],
            [5.0, 11.4])
    R.caption(doc, "表  录制常见问题")

    R.body(doc, "提示：正式录制前先完整走一遍“哑录”——不出声、不保存，只把鼠标和窗口位置走顺，"
                "再开始正式录。这样能省掉一半的重录。", hint=True)

    doc.core_properties.title = "实验 1A 演示视频脚本"
    doc.save(OUT)
    print("saved:", OUT)


if __name__ == "__main__":
    build()
