# 由原答辩 PPT 生成修改版：保留模板背景与装饰图，重排第 2–16 页内容
# 用法：python build_ppt.py base.pptx out.pptx   （base.pptx 为原稿复制两份内容页后的文件）
import sys
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.oxml.ns import qn
from lxml import etree
from PIL import Image

NAVY, BLUE, LBLUE = "1F2A44", "0B5CAD", "EAF2FB"
TEAL, LTEAL = "0E7C70", "E5F3F1"
AMBER, LAMBER = "A86A12", "FBF2E2"
RED, LRED = "C7000B", "FCEBEC"
GRAY, LGRAY, LINE, WHITE = "5B6B82", "F3F6FA", "D3DCE8", "FFFFFF"
FONT = "Microsoft YaHei"
X0, W = 0.75, 11.83


def rgb(h):
    return RGBColor.from_string(h)


def _font(run, size, color, bold=False, name=FONT):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = rgb(color)
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:latin", "a:ea", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = etree.SubElement(rPr, qn(tag))
        el.set("typeface", name)


def fill_tf(tf, paras, size=12, color=NAVY, bold=False, align=PP_ALIGN.LEFT, space_after=3, line=1.15):
    """paras：字符串，或 [(文字, {size,color,bold}), ...]，或 dict(runs=..., bullet=True, align=...)"""
    tf.word_wrap = True
    first = True
    for p in paras:
        para = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        opts = {}
        if isinstance(p, dict):
            opts, p = p, p["runs"]
        if isinstance(p, str):
            p = [(p, {})]
        para.alignment = opts.get("align", align)
        para.line_spacing = opts.get("line", line)
        para.space_after = Pt(opts.get("after", space_after))
        _pPr = para._p.get_or_add_pPr()
        _pPr.set("eaLnBrk", "1"); _pPr.set("hangingPunct", "1"); _pPr.set("latinLnBrk", "0")
        if opts.get("bullet"):
            pPr = para._p.get_or_add_pPr()
            pPr.set("marL", str(int(Inches(0.16))))
            pPr.set("indent", str(-int(Inches(0.16))))
            bc = etree.SubElement(pPr, qn("a:buClr"))
            etree.SubElement(bc, qn("a:srgbClr")).set("val", opts.get("bucolor", BLUE))
            etree.SubElement(pPr, qn("a:buFont")).set("typeface", "Arial")
            etree.SubElement(pPr, qn("a:buChar")).set("char", "•")
        for text, ro in p:
            r = para.add_run()
            r.text = text
            _font(r, ro.get("size", opts.get("size", size)), ro.get("color", opts.get("color", color)),
                  ro.get("bold", opts.get("bold", bold)))


def tb(slide, x, y, w, h, paras, anchor=MSO_ANCHOR.TOP, margin=0.0, name=None, **kw):
    s = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = s.text_frame
    tf.vertical_anchor = anchor
    for side in ("left", "right", "top", "bottom"):
        setattr(tf, f"margin_{side}", Inches(margin))
    fill_tf(tf, paras, **kw)
    if name:
        s.name = name
    return s


def box(slide, x, y, w, h, fill=WHITE, line=LINE, alpha=None, radius=0.08, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
        lw=0.75, name=None):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = min(radius / min(w, h), 0.5)
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = rgb(fill)
        if alpha is not None:
            clr = s.fill._xPr.find(qn("a:solidFill")).find(qn("a:srgbClr"))
            etree.SubElement(clr, qn("a:alpha")).set("val", str(int(alpha * 1000)))
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = rgb(line)
        s.line.width = Pt(lw)
    s.shadow.inherit = False
    s.text_frame.text = ""
    if name:
        s.name = name
    return s


def card(slide, x, y, w, h, fill=WHITE, line=LINE, alpha=88, **kw):
    return box(slide, x, y, w, h, fill=fill, line=line, alpha=alpha, **kw)


def chip(slide, x, y, w, h, text, fill, color, size=10.5, bold=True):
    s = box(slide, x, y, w, h, fill=fill, line=None, radius=h / 2)
    tf = s.text_frame
    for side in ("left", "right", "top", "bottom"):
        setattr(tf, f"margin_{side}", Inches(0.02))
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    fill_tf(tf, [text], size=size, color=color, bold=bold, align=PP_ALIGN.CENTER, space_after=0, line=1.0)
    return s


def circle_num(slide, x, y, d, text, fill=BLUE, color=WHITE, size=11):
    s = box(slide, x, y, d, d, fill=fill, line=None, shape=MSO_SHAPE.OVAL)
    tf = s.text_frame
    for side in ("left", "right", "top", "bottom"):
        setattr(tf, f"margin_{side}", 0)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    fill_tf(tf, [text], size=size, color=color, bold=True, align=PP_ALIGN.CENTER, space_after=0, line=1.0)
    tf.word_wrap = False
    return s


def arrow(slide, x1, y1, x2, y2, color=GRAY, w=1.25, dash=False):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = rgb(color)
    c.line.width = Pt(w)
    ln = c.line._get_or_add_ln()
    if dash:
        etree.SubElement(ln, qn("a:prstDash")).set("val", "dash")
    te = etree.SubElement(ln, qn("a:tailEnd"))
    te.set("type", "triangle"); te.set("w", "med"); te.set("len", "med")
    return c


def node(slide, x, y, w, h, text, fill=LBLUE, line=BLUE, color=NAVY, size=10, bold=True):
    s = box(slide, x, y, w, h, fill=fill, line=line, radius=0.06)
    tf = s.text_frame
    for side in ("left", "right", "top", "bottom"):
        setattr(tf, f"margin_{side}", Inches(0.03))
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    lines = text.split("\n")
    paras = [[(lines[0], {"bold": bold, "size": size})]] + [[(l, {"bold": False, "size": size - 1.5, "color": GRAY})] for l in lines[1:]]
    fill_tf(tf, paras, color=color, align=PP_ALIGN.CENTER, space_after=0, line=1.05)
    return s


def picture(slide, path, x, y, w=None, h=None, border=True):
    iw, ih = Image.open(path).size
    if w is None:
        w = h * iw / ih
    if h is None:
        h = w * ih / iw
    p = slide.shapes.add_picture(path, Inches(x), Inches(y), Inches(w), Inches(h))
    if border:
        p.line.color.rgb = rgb(LINE)
        p.line.width = Pt(0.75)
    return p, w, h


def table(slide, x, y, w, col_w, rows, header, size=10, row_h=0.3, head_fill=NAVY, zebra=True, bold_first=False,
          aligns=None):
    nrow, ncol = len(rows) + 1, len(header)
    gf = slide.shapes.add_table(nrow, ncol, Inches(x), Inches(y), Inches(w), Inches(row_h * nrow))
    t = gf.table
    tblPr = gf._element.graphic.graphicData.tbl.tblPr
    sid = tblPr.find(qn("a:tableStyleId"))
    if sid is None:
        sid = etree.SubElement(tblPr, qn("a:tableStyleId"))
    sid.text = "{2D5ABB26-0587-4C30-8999-92F81FD0307C}"
    tot = sum(col_w)
    for i, cw in enumerate(col_w):
        t.columns[i].width = Inches(w * cw / tot)
    for r in range(nrow):
        t.rows[r].height = Inches(row_h)
        for c in range(ncol):
            cell = t.cell(r, c)
            val = header[c] if r == 0 else rows[r - 1][c]
            cell.margin_left = cell.margin_right = Inches(0.06)
            cell.margin_top = cell.margin_bottom = Inches(0.025)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            tcPr = cell._tc.get_or_add_tcPr()
            for tag in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
                ln = etree.SubElement(tcPr, qn(tag))
                if tag == "a:lnB":
                    ln.set("w", str(int(Pt(0.5)))); sf = etree.SubElement(ln, qn("a:solidFill"))
                    etree.SubElement(sf, qn("a:srgbClr")).set("val", LINE)
                else:
                    ln.set("w", "0"); etree.SubElement(ln, qn("a:noFill"))
            cell.fill.solid()
            if r == 0:
                cell.fill.fore_color.rgb = rgb(head_fill)
            else:
                cell.fill.fore_color.rgb = rgb(LGRAY if (zebra and r % 2 == 0) else WHITE)
            al = (aligns[c] if aligns else PP_ALIGN.LEFT)
            if isinstance(val, str):
                runs = [(val, {})]
            else:
                runs = val
            cell.text_frame.paragraphs[0].text = ""
            fill_tf(cell.text_frame, [dict(runs=runs, align=PP_ALIGN.CENTER if r == 0 else al)], size=size,
                    color=WHITE if r == 0 else NAVY, bold=(r == 0) or (bold_first and c == 0), space_after=0, line=1.05)
    return gf


def title(slide, text, sub=None):
    tb(slide, X0, 0.42, W, 0.55, [text], size=24, bold=True, color=NAVY, anchor=MSO_ANCHOR.MIDDLE)
    if sub:
        tb(slide, X0, 0.98, W, 0.34, [sub], size=13, color=GRAY, anchor=MSO_ANCHOR.MIDDLE)


def footnote(slide, text):
    tb(slide, 2.55, 6.36, 8.8, 0.42, [text], size=9.5, color=GRAY, anchor=MSO_ANCHOR.TOP, line=1.1)


def section_label(slide, x, y, w, text, color=BLUE, size=13.5):
    tb(slide, x, y, w, 0.32, [text], size=size, bold=True, color=color, anchor=MSO_ANCHOR.MIDDLE)


def clear(slide):
    keep = {"Picture 2", "Picture 3", "Picture 4", "Picture 5"}
    for sh in list(slide.shapes):
        if sh.shape_type == MSO_SHAPE_TYPE.PICTURE and sh.name in keep:
            continue
        sh._element.getparent().remove(sh._element)


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def chart_style(ch, size=10):
    ch.font.size = Pt(size)
    ch.font.name = FONT
    ch.font.color.rgb = rgb(GRAY)


def kpi(slide, x, y, w, h, num, label, color=BLUE, num_w=None, num_size=22, label_size=10.5):
    card(slide, x, y, w, h)
    nw = num_w or 1.15
    tb(slide, x + 0.15, y, nw, h, [num], size=num_size, bold=True, color=color, anchor=MSO_ANCHOR.MIDDLE)
    tb(slide, x + 0.15 + nw, y + 0.04, w - nw - 0.27, h - 0.08, label.split("\n"), size=label_size, color=GRAY,
       anchor=MSO_ANCHOR.MIDDLE, line=1.1, space_after=0)


ROLE = {"疑似受骗付款端": ("EAB8BC", "B5545C"), "一级收款端": ("F4C47E", "B07A1F"), "中转端": ("F1DF7C", "A08A1E"),
        "末端": ("B9DBAC", "4E8A3E")}


def draw_chain(slide, x, y, w, h, nodes, edges, d=0.58):
    pos = {}
    for k, (rx, ry, role) in nodes.items():
        cx, cy = x + rx * w, y + ry * h
        pos[k] = (cx, cy)
        fc, lc = ROLE[role]
        c = circle_num(slide, cx - d / 2, cy - d / 2, d, k, fill=fc, color=NAVY, size=8)
        c.line.color.rgb = rgb(lc)
        c.line.width = Pt(1)
        tb(slide, cx - 0.65, cy + d / 2 + 0.01, 1.3, 0.22, [role], size=8, color=GRAY, align=PP_ALIGN.CENTER)
    for a, b, lab in edges:
        (x1, y1), (x2, y2) = pos[a], pos[b]
        dx, dy = x2 - x1, y2 - y1
        L = (dx * dx + dy * dy) ** 0.5
        ux, uy = dx / L, dy / L
        r = d / 2 + 0.02
        arrow(slide, x1 + ux * r, y1 + uy * r, x2 - ux * r, y2 - uy * r, color="6B7A90", w=1.25)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        tb(slide, mx - 0.5, my - 0.4, 1.0, 0.36, lab.split(" · "), size=8, color=NAVY, align=PP_ALIGN.CENTER,
           anchor=MSO_ANCHOR.BOTTOM, line=1.0, space_after=0)


# ---------------------------------------------------------------- 各页内容

def s_pain(s):
    title(s, "当前痛点：涉诈资金链路隐蔽，人工研判低效", "单笔流水往往看似正常，风险体现在多个账户、多个时间点连成的结构上")
    section_label(s, X0, 1.48, 7.2, "三类常见资金转移手法")
    pats = [
        ("快进快出", "R01 · R04", "资金到账后数十分钟内几乎全额转出或取现；单笔金额正常，异常在时间衔接。"),
        ("分层中转", "R07 多层链路", "资金经多个中转账户逐层转移，每一跳金额略减；单笔看均为普通转账。"),
        ("拆分转出", "R03 拆分转出", "大额资金拆成多笔小额分散转出，每笔低于 1 万元，合计才显出规模。"),
    ]
    cw, gap, cy, ch = 2.33, 0.2, 1.88, 2.72
    for i, (name, rule, desc) in enumerate(pats):
        x = X0 + i * (cw + gap)
        card(s, x, cy, cw, ch)
        tb(s, x + 0.15, cy + 0.12, 1.2, 0.32, [name], size=13, bold=True, anchor=MSO_ANCHOR.MIDDLE)
        chip(s, x + cw - 1.08, cy + 0.15, 0.95, 0.26, rule, LBLUE, BLUE, size=8.5)
        dy = cy + 0.75
        if i == 0:
            xs = [x + 0.12, x + 0.9, x + 1.68]
            for xx, t in zip(xs, ["A", "B", "取现"]):
                node(s, xx, dy + 0.2, 0.55, 0.34, t, fill=LRED if t == "A" else LBLUE, line=RED if t == "A" else BLUE)
            arrow(s, xs[0] + 0.55, dy + 0.37, xs[1], dy + 0.37)
            arrow(s, xs[1] + 0.55, dy + 0.37, xs[2], dy + 0.37)
            tb(s, x + 0.55, dy + 0.62, 1.3, 0.25, ["≤ 60 分钟"], size=8.5, color=GRAY, align=PP_ALIGN.CENTER)
        elif i == 1:
            xs = [x + 0.1, x + 0.65, x + 1.2, x + 1.75]
            for xx, t in zip(xs, ["A", "M1", "M2", "B"]):
                node(s, xx, dy + 0.2, 0.45, 0.34, t, fill=LRED if t == "A" else LBLUE, line=RED if t == "A" else BLUE)
            for a, b in zip(xs, xs[1:]):
                arrow(s, a + 0.45, dy + 0.37, b, dy + 0.37)
        else:
            node(s, x + 0.22, dy + 0.2, 0.5, 0.34, "A", fill=LRED, line=RED)
            for k in range(3):
                yy = dy - 0.12 + k * 0.38
                node(s, x + 1.5, yy, 0.55, 0.3, f"B{k + 1}")
                arrow(s, x + 0.72, dy + 0.37, x + 1.5, yy + 0.15)
        tb(s, x + 0.15, cy + 1.78, cw - 0.3, 0.85, [desc], size=10.5, color=GRAY, line=1.2)
    rx, rw = 8.4, 4.18
    section_label(s, rx, 1.48, rw, "人工研判四步及其难点")
    steps = [("翻流水", "逐笔查阅数千条流水，链上交易混在日常交易中"),
             ("连路径", "手工拼接资金路径，付款方与收款方容易颠倒"),
             ("查规则", "逐条对照阈值与时间窗，规则调整后需逐户重核"),
             ("写说明", "证据格式不统一，交易编号易抄错，复核困难")]
    for i, (a, b) in enumerate(steps):
        y = 1.88 + i * 0.7
        card(s, rx, y, rw, 0.62)
        circle_num(s, rx + 0.14, y + 0.14, 0.34, f"{i + 1:02d}", size=9.5)
        tb(s, rx + 0.6, y + 0.04, 0.8, 0.54, [a], size=12, bold=True, anchor=MSO_ANCHOR.MIDDLE)
        tb(s, rx + 1.38, y + 0.04, rw - 1.5, 0.54, [b], size=10.5, color=GRAY, anchor=MSO_ANCHOR.MIDDLE, line=1.1)
    facts = [("1.9%", RED, "本数据集 2,973 笔交易中，埋入链上的转账只有 57 笔，混在 2,872 笔日常互转和消费里"),
             ("48 户", AMBER, "按单笔 ≥1 万元告警（基线 B1）时，需人工复核的账户达 48 户，其中 2 户为干扰账户"),
             ("8 户", BLUE, "R01 时间窗由 60 分钟改为 120 分钟后，300 户中有 8 户结论变化，需要重新核对")]
    fw = (W - 0.4) / 3
    for i, (n, c, t) in enumerate(facts):
        x = X0 + i * (fw + 0.2)
        kpi(s, x, 4.8, fw, 1.25, n, t, color=c, num_w=1.1, num_size=22, label_size=10.5)
    footnote(s, "注：数字来自本作品合成数据集 sim-gen_profile_v1-seed42 及离线评测结果。")
    notes(s, "为什么强调看链路而不是看单笔。快进快出、分层中转、拆分转出三类手法里，任何一笔单独看都可能正常，"
             "只有把时间、账户衔接和资金流向连起来才能还原链路。我们的数据里，链上转账只占全部交易的 1.9%；"
             "如果只按单笔金额告警，48 户要人工复核；规则口径一变，又有 8 户结论要重核。这就是人工翻流水、连路径、查规则、写说明的难点。")


def s_idea(s):
    title(s, "破题思路：把合成流水转成可复核线索，输出人工复核工单", "确定性计算交给算法，理解请求与组织证据交给智能体")
    y, h = 1.55, 3.75
    # 输入
    card(s, X0, y, 3.3, h)
    section_label(s, X0 + 0.2, y + 0.15, 3.0, "输入 INPUT")
    ins = [("账户清单", "300 个合成账户，含类型与开户日期"), ("交易流水", "2,973 笔：时间、金额、付款方、收款方、类型"),
           ("规则版本", "v1 / v2 YAML，参数可配置"), ("知识库", "仿真规则、公开案例、监管文件、法规原文")]
    for i, (a, b) in enumerate(ins):
        tb(s, X0 + 0.2, y + 0.62 + i * 0.75, 2.95, 0.7, [[(a, {"bold": True, "size": 12})], [(b, {"size": 10.5, "color": GRAY})]],
           line=1.1, space_after=2)
    box(s, 4.12, y + h / 2 - 0.17, 0.32, 0.34, fill=BLUE, line=None, shape=MSO_SHAPE.RIGHT_ARROW)
    # 处理
    px, pw = 4.55, 4.35
    card(s, px, y, pw, h, fill=LBLUE, line="B9CDE6")
    section_label(s, px + 0.2, y + 0.15, pw - 0.4, "链路研判：智能体 + MCP 工具")
    steps = [("get_account / get_transactions", "查询账户画像与流水"), ("trace_chain", "时序与资金守恒追链"),
             ("check_rules", "风险命中与反向证据"), ("knowledge_base_search", "检索规则定义与出处"),
             ("make_ticket", "生成结构化研判工单")]
    for i, (a, b) in enumerate(steps):
        yy = y + 0.6 + i * 0.6
        circle_num(s, px + 0.2, yy + 0.08, 0.32, str(i + 1), size=10)
        tb(s, px + 0.65, yy, pw - 0.8, 0.5, [[(a, {"bold": True, "size": 11, "color": BLUE})], [(b, {"size": 10, "color": GRAY})]],
           line=1.0, space_after=0)
    box(s, 9.0, y + h / 2 - 0.17, 0.32, 0.34, fill=BLUE, line=None, shape=MSO_SHAPE.RIGHT_ARROW)
    # 输出
    ox, ow = 9.43, X0 + W - 9.43
    card(s, ox, y, ow, h, fill=LTEAL, line="B5DAD4")
    section_label(s, ox + 0.2, y + 0.15, ow - 0.4, "输出 OUTPUT：人工复核工单", color=TEAL)
    outs = ["可疑资金链路与账户角色", "四档状态判定", "支持证据 + 反向证据（附交易编号）", "缺失证据与规则依据", "建议动作（三种，供人工复核）"]
    tb(s, ox + 0.2, y + 0.62, ow - 0.35, 2.0, [dict(runs=[(t, {})], bullet=True, bucolor=TEAL, after=5) for t in outs], size=11.5)
    box(s, ox + 0.2, y + 2.6, ow - 0.4, 0.98, fill=WHITE, line="B5DAD4", alpha=90)
    tb(s, ox + 0.32, y + 2.62, ow - 0.6, 0.94, [[("示例（A0209 / v1）", {"bold": True, "color": TEAL, "size": 10})],
                                              [("链 L-T01908 · 中转端 · 命中 4 条规则", {"size": 10})],
                                              [("状态：建议人工复核", {"size": 10, "bold": True, "color": RED})]],
       line=1.05, space_after=1, anchor=MSO_ANCHOR.MIDDLE)
    card(s, X0, 5.5, W, 0.7, fill=LAMBER, line="E9D3A6")
    tb(s, X0 + 0.2, 5.5, W - 0.4, 0.7, [[("能力边界：", {"bold": True, "color": AMBER}),
                                          ("系统给出辅助研判意见，不作违法或诈骗认定；建议动作限定为建议人工复核、建议关注后续交易、建议补充材料三种；"
                                           "所用数据均为合成数据，结论在本仿真场景内成立。", {})]], size=11, anchor=MSO_ANCHOR.MIDDLE)
    notes(s, "这一页讲系统做什么。左边是输入：账户、流水、规则版本和知识库；中间是智能体按固定顺序调用五类工具；"
             "右边输出一张人工复核工单，包括链路、角色、正反两方面证据、缺口和建议动作。底部是能力边界：不做违法认定、不冻结不处罚，数据全是合成的。")


def s_system(s):
    title(s, "系统构成：数据规范、算法与 MCP、Nexent 智能体、知识库与评测", "四个模块分别交付，可在本地一键复现核验")
    mods = [
        ("01", "数据与规范", ["300 账户、2,973 笔交易、12 条埋入链，SHA256 冻结", "数据、规则、判定与输出三份规范及 JSON Schema", "规则 YAML v1 / v2，阈值为仿真设定", "标注答案与工具代码隔离，泄题检查自动执行"], "data/ · Data and Rules/"),
        ("02", "算法与 MCP", ["trace：时序 + 资金守恒追链", "R01–R11 规则引擎、工单判定、版本重判", "FastMCP 服务 8 个工具，real 模式", "云端 systemd 常驻，自检 19 次调用通过"], "core/ · mcp_server/"),
        ("03", "Nexent 智能体", ["当前发布 fundtrace-v1.4（平台第 11 版）", "DeepSeek-V4.1-Flash，最大 15 步", "7 个业务工具 + 3 个 Skill 按意图编排", "答复分“工具事实”与“规则定义与来源”两区"], "agent/"),
        ("04", "知识库与评测", ["4 个知识库共 59 份文档（3 + 5 + 41 + 10）", "离线评测、基线 B1 / B2、链路图", "pytest 87 项全部通过", "检索测试集 50 题，答复编号回查脚本"], "kb/ · eval/ · tests/"),
    ]
    cw, gap, y, h = 2.8, 0.21, 1.55, 4.0
    for i, (n, name, items, path) in enumerate(mods):
        x = X0 + i * (cw + gap)
        card(s, x, y, cw, h)
        tb(s, x + 0.2, y + 0.15, 0.8, 0.5, [n], size=22, bold=True, color=BLUE, anchor=MSO_ANCHOR.MIDDLE)
        tb(s, x + 0.2, y + 0.68, cw - 0.4, 0.38, [name], size=14.5, bold=True)
        tb(s, x + 0.2, y + 1.12, cw - 0.35, 2.4, [dict(runs=[(t, {})], bullet=True, after=6) for t in items], size=11, line=1.15)
        chip(s, x + 0.2, y + h - 0.48, cw - 0.4, 0.3, path, LGRAY, GRAY, size=9, bold=False)
    flow = ["冻结数据", "算法与规则", "MCP 工具", "智能体编排", "辅助研判工单"]
    fw, fy = 1.9, 5.78
    step = (W - fw) / 4
    for i, t in enumerate(flow):
        x = X0 + i * step
        node(s, x, fy, fw, 0.4, t, fill=LBLUE if i < 4 else LTEAL, line=BLUE if i < 4 else TEAL, size=10.5)
        if i < 4:
            arrow(s, x + fw + 0.03, fy + 0.2, x + step - 0.03, fy + 0.2, color=BLUE)
    notes(s, "系统分四块：一是冻结的数据和三份规范；二是追链、规则引擎和 MCP 服务；三是 Nexent 智能体，目前发布到 v1.4，加载三个 Skill；"
             "四是四个知识库和评测脚本。每一块都有对应目录，可以在本地一键核验。本体演化、真实数据、OCR/GNN 等还没做，不当成已完成。")


def s_data(s):
    title(s, "数据集设计：300 账户、2,973 笔交易、12 条埋入链", "随机种子 42 生成并冻结，相同种子可逐字节复现；标注答案单独存放在 eval/，工具代码不可读取")
    k = [("300", "合成账户\n个人 250 · 商户 30 · 企业 20", BLUE, 0.78), ("2,973", "合成交易流水\n分钟级时间戳", BLUE, 1.12),
         ("12", "埋入涉诈资金链\n单笔受骗 2.5–5 万元", RED, 0.55), ("7 天", "2026-03-01 至 03-07\nAsia/Shanghai", TEAL, 0.92)]
    kw = (W - 0.6) / 4
    for i, (n, l, c, nw) in enumerate(k):
        kpi(s, X0 + i * (kw + 0.2), 1.5, kw, 0.82, n, l, color=c, num_w=nw, num_size=21, label_size=10)
    # 交易构成
    cx, cy, cw, chh = X0, 2.5, 6.15, 3.7
    card(s, cx, cy, cw, chh)
    section_label(s, cx + 0.2, cy + 0.1, 4, "交易构成（笔）", size=12.5)
    cd = CategoryChartData()
    cats = ["提现到现金", "合租转发", "工资", "链上转账（埋入链）", "个人小额互转", "消费"]
    vals = [11, 2, 31, 57, 1400, 1472]
    cd.categories = cats
    cd.add_series("笔数", vals)
    gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(cx + 0.1), Inches(cy + 0.45), Inches(cw - 0.25), Inches(chh - 0.55), cd)
    ch = gf.chart
    chart_style(ch)
    ch.has_title = False
    ch.has_legend = False
    pl = ch.plots[0]
    pl.gap_width = 45
    pl.has_data_labels = True
    pl.data_labels.number_format = "#,##0"
    pl.data_labels.number_format_is_linked = False
    pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
    pl.data_labels.font.size = Pt(10)
    pl.data_labels.font.color.rgb = rgb(NAVY)
    ser = pl.series[0]
    ser.format.fill.solid(); ser.format.fill.fore_color.rgb = rgb("8FB3DE")
    pt = ser.points[3]
    pt.format.fill.solid(); pt.format.fill.fore_color.rgb = rgb(RED)
    va = ch.value_axis
    va.visible = False
    va.has_major_gridlines = False
    va.maximum_scale = 1750
    ca = ch.category_axis
    ca.format.line.color.rgb = rgb(LINE)
    ca.tick_labels.font.size = Pt(10)
    ca.tick_labels.font.color.rgb = rgb(NAVY)
    # 右侧
    rx, rw = X0 + cw + 0.2, W - cw - 0.2
    card(s, rx, 2.5, rw, 1.6)
    section_label(s, rx + 0.2, 2.58, 3, "12 条埋入链的手法分布", size=12.5)
    chains = [("快进快出", 6, "到账后短时转出或取现"), ("分层中转", 3, "经多个中转账户逐层转移"), ("拆分转出", 3, "拆成多笔小额分散转出")]
    for i, (n, c, d) in enumerate(chains):
        yy = 2.98 + i * 0.36
        tb(s, rx + 0.2, yy, 0.95, 0.3, [n], size=10.5, bold=True, anchor=MSO_ANCHOR.MIDDLE)
        box(s, rx + 1.15, yy + 0.07, 0.3 * c, 0.17, fill=RED if i == 0 else "E7868B", line=None, radius=0.03)
        tb(s, rx + 1.2 + 0.3 * c, yy, 0.55, 0.3, [f"{c} 条"], size=10.5, bold=True, color=RED, anchor=MSO_ANCHOR.MIDDLE)
        tb(s, rx + 3.4, yy, rw - 3.5, 0.3, [d], size=10, color=GRAY, anchor=MSO_ANCHOR.MIDDLE)
    card(s, rx, 4.25, rw, 1.95)
    section_label(s, rx + 0.2, 4.32, 4, "同期混入的干扰场景（检验误报）", size=12.5)
    rows = [("正常工资", "R09 反向证据，写入工单供人工判断"), ("高频商户收款", "R10 反向证据；与 R02 同时命中时判“证据不足”"),
            ("合租转发房租", "v2 时间窗放宽后成链，判“存在风险信号”")]
    for i, (a, b) in enumerate(rows):
        yy = 4.7 + i * 0.33
        tb(s, rx + 0.2, yy, 1.35, 0.3, [a], size=10.5, bold=True, anchor=MSO_ANCHOR.MIDDLE)
        tb(s, rx + 1.55, yy, rw - 1.7, 0.3, [b], size=10, color=GRAY, anchor=MSO_ANCHOR.MIDDLE)
    tb(s, rx + 0.2, 5.75, rw - 0.4, 0.35, [[("结果：", {"bold": True, "color": TEAL}),
                                           ("63 个干扰账户在 v1、v2 下均未被判为“建议人工复核”", {"color": TEAL})]], size=10.5, anchor=MSO_ANCHOR.MIDDLE)
    footnote(s, "注：开发集为单一随机种子 seed42，各项指标基于本数据集口径计算。")
    notes(s, "这是可控实验用的数据集：300 个账户、2973 笔交易，时间跨度 7 天。交易里绝大多数是消费和个人小额互转，埋入的 12 条链只有 57 笔转账，"
             "6 条快进快出、3 条分层中转、3 条拆分转出。另外混入工资、商户收款、合租转发三类干扰，用来测误报：63 个干扰账户在两个版本下都没有被判为建议人工复核。"
             "这是单一种子的开发集，不代表真实分布。")


def s_trace(s):
    title(s, "链路追踪约束：时序与资金守恒让每一步链路都可解释、可回查", "以平台实测链 L-T01908 为例")
    lx, lw = X0, 4.75
    section_label(s, lx, 1.48, lw, "候选边须同时满足四条约束")
    cons = [("账户衔接", "前一笔的收款方即后一笔的付款方"), ("时间递增", "后一笔交易严格晚于前一笔"),
            ("时间窗内", "间隔不超过规则时间窗：v1 为 60 分钟，v2 为 120 分钟"), ("资金守恒", "中转账户时间窗内转入与转出满足守恒比例，不凭空增减")]
    for i, (a, b) in enumerate(cons):
        y = 1.9 + i * 0.78
        card(s, lx, y, lw, 0.68)
        circle_num(s, lx + 0.15, y + 0.17, 0.34, f"{i + 1:02d}", size=9.5)
        tb(s, lx + 0.62, y + 0.04, 3.95, 0.6, [[(a, {"bold": True, "size": 12})], [(b, {"size": 10.5, "color": GRAY})]], line=1.05,
           space_after=1, anchor=MSO_ANCHOR.MIDDLE)
    card(s, lx, 5.05, lw, 1.15, fill=LBLUE, line="B9CDE6")
    tb(s, lx + 0.2, 5.1, lw - 0.35, 1.05, [[("候选边：", {"bold": True, "color": BLUE}), ("类型为转账、双方均为已知账户、金额 ≥3,000 元", {})],
                                          [("保留链：", {"bold": True, "color": BLUE}), ("链内至少一笔 ≥10,000 元；弱连通分量即候选链", {})]],
       size=10.5, line=1.2, space_after=4, anchor=MSO_ANCHOR.MIDDLE)
    rx, rw = 5.75, X0 + W - 5.75
    card(s, rx, 1.48, rw, 3.25)
    section_label(s, rx + 0.2, 1.55, rw - 0.4, "实测示例：资金链 L-T01908（规则 v1，合成数据）", size=12.5)
    draw_chain(s, rx + 0.55, 2.05, rw - 1.1, 1.5,
               {"A0044": (0.0, 0.12, "疑似受骗付款端"), "A0287": (0.0, 0.88, "疑似受骗付款端"), "A0283": (0.3, 0.5, "一级收款端"),
                "A0209": (0.55, 0.5, "中转端"), "A0177": (0.78, 0.5, "中转端"), "A0186": (1.0, 0.5, "末端")},
               [("A0044", "A0283", "35,710 元 · 14:28"), ("A0287", "A0283", "36,059 元 · 14:33"), ("A0283", "A0209", "70,850 元 · 15:04"),
                ("A0209", "A0177", "70,396 元 · 15:14"), ("A0177", "A0186", "70,093 元 · 15:20")])
    ty = 3.88
    tb(s, rx + 0.2, ty, rw - 0.4, 4.65 - ty, [
        dict(runs=[("14:28、14:33 A0044、A0287 并行汇入 A0283，图中保留两条分支，不串成一条路径", {})], bullet=True, after=3),
        dict(runs=[("15:04 转入 A0209（中转端），15:14 转 A0177，15:20 到 A0186（末端），4 跳共 52 分钟", {})], bullet=True, after=3),
        dict(runs=[("链金额只统计源交易 71,769 元，不把各跳金额累加", {})], bullet=True, after=0)], size=10.5, line=1.15)
    section_label(s, rx, 4.88, rw, "追链五步", size=12.5)
    st = ["筛选候选边", "衔接与时间窗", "资金守恒", "弱连通分量成链", "最长路径与角色"]
    sw, sg = 1.18, (rw - 5 * 1.18) / 4
    for i, t in enumerate(st):
        x = rx + i * (sw + sg)
        node(s, x, 5.3, sw, 0.6, f"{i + 1}\n{t}" if False else t, size=10)
        if i < 4:
            arrow(s, x + sw + 0.02, 5.6, x + sw + sg - 0.02, 5.6, color=BLUE)
    footnote(s, "说明：v2 仅把仿真时间窗参数由 60 分钟放宽到 120 分钟，账户与交易本身不变；参数见 rules_v*.yaml。")
    notes(s, "链路怎么算出来：候选边要同时满足账户衔接、时间递增、落在时间窗内、资金守恒四条约束。右边是平台实测的 L-T01908："
             "A0044 和 A0287 并行汇入 A0283，再经 A0209、A0177 到 A0186，4 跳 52 分钟。两个付款方是两条并行分支，不能画成一条路径；"
             "链金额只算源交易 71769 元。v1 和 v2 的差别只是时间窗从 60 分钟放宽到 120 分钟。")


def s_rules(s):
    title(s, "规则引擎：把链路与账户事实转为四档状态工单", "规则在 YAML 中声明，按版本计算；每条命中都附证据交易编号")
    flow = ["账户与流水", "trace 链路追踪", "R01–R11 规则判定", "输出复核工单"]
    fw = 2.55
    step = (W - fw) / 3
    for i, t in enumerate(flow):
        x = X0 + i * step
        node(s, x, 1.5, fw, 0.42, t, fill=LBLUE if i < 3 else LTEAL, line=BLUE if i < 3 else TEAL, size=11)
        if i < 3:
            arrow(s, x + fw + 0.03, 1.71, x + step - 0.03, 1.71, color=BLUE)
    rules = [("R01", "快进快出", "风险/高", "60 分钟内转出达转入的 90%–110%，转入 ≥1 万元"),
             ("R02", "短时多来源集中转入", "风险/中", "连续 60 分钟内转入来源 ≥3 个"),
             ("R03", "拆分转出", "风险/高", "60 分钟内向 ≥4 个账户转出，每笔 ≤9,999 元"),
             ("R04", "余额清零", "风险/中", "单日转入 ≥1 万元，当日转出达 95%–110%"),
             ("R05", "新开账户大额转入", "风险/中", "开户不足 30 天，单日转入 >2 万元"),
             ("R06", "夜间大额", "风险/中", "0:00–4:59 单笔 >1 万元"),
             ("R07", "多层链路", "风险/高", "位于资金链上，且最长路径 ≥3 跳"),
             ("R08", "首次对手大额转入", "风险/中", "单笔 >2 万元，且此前与该对手无交易"),
             ("R09", "稳定工资收入", "反向/低", "有工资入账"),
             ("R10", "商户经营特征", "反向/低", "商户；≥10 个付款方，中位数 ≤500 元"),
             ("R11", "多个首次对手集中转入", "风险/中", "v2 新增：24 小时内 ≥2 个首次对手各转入 >1 万元")]
    rws = []
    for a, b, c, d in rules:
        col = TEAL if c.startswith("反向") else NAVY
        rws.append([[(a, {"bold": True, "color": BLUE})], b, [(c, {"color": col})], d])
    table(s, X0, 2.12, 7.15, [0.55, 1.75, 0.8, 4.05], rws, ["编号", "名称", "类型", "关键条件（v1 参数）"], size=9.5, row_h=0.295)
    rx, rw = 8.12, X0 + W - 8.12
    section_label(s, rx, 2.1, rw, "四档状态（按顺序判定，命中即停）", size=12.5)
    sts = [("未见异常", "CLEAR", "无风险规则命中，且不在链上", "221 / 215", TEAL, LTEAL),
           ("建议人工复核", "REVIEW", "命中 ≥2 条风险规则，在链上且为一级收款端、中转端或拆分端", "16 / 18", RED, LRED),
           ("证据不足", "INSUFFICIENT", "同时命中风险规则和反向规则", "11 / 12", AMBER, LAMBER),
           ("存在风险信号", "RISK_SIGNAL", "其他情况：有风险命中，或位于链上", "52 / 55", BLUE, LBLUE)]
    for i, (n, code, cond, cnt, c, lc) in enumerate(sts):
        y = 2.5 + i * 0.84
        card(s, rx, y, rw, 0.76, fill=lc, line=None, alpha=95)
        tb(s, rx + 0.15, y + 0.06, 2.5, 0.3, [[(f"{i + 1}. {n}", {"bold": True, "color": c, "size": 11.5}), (f"  {code}", {"size": 9, "color": c})]],
           anchor=MSO_ANCHOR.MIDDLE)
        tb(s, rx + 0.15, y + 0.37, rw - 1.35, 0.36, [cond], size=9.5, color=NAVY, line=1.05, anchor=MSO_ANCHOR.MIDDLE)
        tb(s, rx + rw - 1.2, y + 0.06, 1.08, 0.64, [[("v1 / v2 户数", {"size": 8, "color": GRAY})], [(cnt, {"size": 12, "bold": True, "color": c})]],
           align=PP_ALIGN.RIGHT, line=1.0, space_after=0, anchor=MSO_ANCHOR.MIDDLE)
    card(s, X0, 5.95, W, 0.3, fill=None, line=None)
    tb(s, X0, 5.92, W, 0.36, [[("反向规则保留但不自动抵消风险：", {"bold": True, "color": TEAL}),
                               ("R09、R10 写入工单反向证据；顺序 2 先于 3，有工资入账的中转账户仍判“建议人工复核”。", {})]],
       size=10.5, anchor=MSO_ANCHOR.MIDDLE)
    notes(s, "规则引擎：账户流水先经 trace 连出链路，再按 R01 到 R11 判定，最后输出四档状态工单。左边是全部 11 条规则，阈值都是仿真设定；"
             "右边是判定顺序，命中即停，并附了 v1、v2 下各档的账户数。R09 工资和 R10 商户是反向证据，写进工单，但不会把风险链自动抵消。")


def s_mcp(s):
    title(s, "MCP 工具调用架构：确定性业务计算交给工具，知识库只作解释", "fundtrace MCP 共 8 个工具：hello + 7 个业务工具")
    ns = [("Nexent 智能体", "涉诈资金链路研判助手"), ("fundtrace MCP", "FastMCP · SSE · 8900"),
          ("core.api", "追链 / 规则 / 工单 / 重判"), ("data / tickets", "合成 CSV · 工单 JSON")]
    nw, gap = 2.45, (W - 4 * 2.45) / 3
    for i, (a, b) in enumerate(ns):
        x = X0 + i * (nw + gap)
        node(s, x, 1.48, nw, 0.68, f"{a}\n{b}", fill=LBLUE if i else "E8E6F7", line=BLUE if i else "6B5FB5", size=11.5)
        if i < 3:
            arrow(s, x + nw + 0.04, 1.82, x + nw + gap - 0.04, 1.82, color=BLUE, w=1.5)
    arrow(s, X0 + 0.6, 2.18, X0 + 0.6, 2.55, color=AMBER, dash=True)
    node(s, X0, 2.57, 6.4, 0.46, "knowledge_base_search → 4 个知识库（由 Nexent 提供，只作解释，不作账户事实）", fill=LAMBER, line="E1BE7C", size=10.5, bold=False)
    tools = [("get_account", "账户画像", "类型、开户日期、交易统计"), ("get_transactions", "流水查询", "total、count、truncated 截断标志"),
             ("trace_chain", "资金链追踪", "有向交易边、账户角色、链金额"), ("check_rules", "规则判定", "hits 风险命中、counter 反向命中"),
             ("make_ticket", "生成工单", "状态、证据、缺口、建议动作"), ("get_ticket", "读取工单", "已保存工单，不重新计算"),
             ("rejudge", "版本重判", "全部账户的状态变化与原因")]
    rws = [[[(a, {"bold": True, "color": BLUE})], b, c] for a, b, c in tools]
    table(s, X0, 3.2, 6.4, [1.75, 1.2, 3.45], rws, ["业务工具", "用途", "关键返回"], size=9.5, row_h=0.36)
    rx, rw = 7.35, X0 + W - 7.35
    _, pw, ph = picture(s, "img/mcp.png", rx, 2.57, w=rw)
    tb(s, rx, 2.57 + ph + 0.04, rw, 0.3, ["截图：Nexent MCP 服务配置，fundtrace 已启用，连通性校验成功（内网地址已遮盖）"], size=9, color=GRAY)
    cy = 2.57 + ph + 0.42
    card(s, rx, cy, rw, 6.2 - cy)
    tb(s, rx + 0.2, cy + 0.08, rw - 0.35, 6.2 - cy - 0.15, [
        dict(runs=[("real 模式：", {"bold": True}), ("7 个业务工具调用 core 算法，处理完整合成数据", {})], bullet=True, after=4),
        dict(runs=[("统一错误对象：", {"bold": True}), ("{error, code, detail}，5 种错误码，智能体据此报告失败步骤", {})], bullet=True, after=4),
        dict(runs=[("自检与常驻：", {"bold": True}), ("selftest 8 工具 19 次协议调用通过；systemd 开机自启、异常自动重启", {})], bullet=True, after=0)],
       size=10.5, line=1.15, anchor=MSO_ANCHOR.MIDDLE)
    footnote(s, "说明：“real 模式”指真实调用算法处理合成数据，不代表银行真实数据；知识库检索不计入 8 个 MCP 服务工具。")
    notes(s, "主链路是 Nexent 智能体通过 SSE 调用 fundtrace MCP，MCP 调 core.api 计算链路、规则和工单，最后读写合成数据和工单文件。"
             "旁路是知识库检索，由 Nexent 自己提供，只用来解释规则。左下是 7 个业务工具各自返回什么；右边截图是平台上 MCP 服务已启用、连通性校验成功。"
             "云端自检 8 个工具、19 次协议调用全部通过，由 systemd 常驻。")


def s_skills(s):
    title(s, "三个 Skill：规范流程与输出，计算仍由底层工具完成", "研判类请求先加载 Skill，再按 Skill 规定的顺序调用工具")
    sk = [("Skill 1", "evidence-citation", "所有输出结论或工单的请求",
           "交易证据写成“编号（时间 付款方→收款方 金额）”，信息取自本次工具返回；保留支持、反向、缺失证据和原有建议动作"),
          ("Skill 2", "fund-chain-investigation", "单账户研判、追踪资金去向",
           "画像 → 流水 → 追链 → 规则 → 检索 → 工单 → 核对，任一步失败即停止，不补造结果；答复按结论、支持、反向、缺失证据与规则依据五项组织"),
          ("Skill 3", "rule-update-rejudge", "规则版本比较与重判",
           "先 rejudge 再检索规则差异，列出全部变化账户；用户指定账户后才生成新版本工单；说明变化来自规则口径调整")]
    lw = 6.35
    for i, (a, n, sc, d) in enumerate(sk):
        y = 1.48 + i * 1.18
        card(s, X0, y, lw, 1.08)
        chip(s, X0 + 0.18, y + 0.15, 0.72, 0.27, a, BLUE, WHITE, size=9)
        tb(s, X0 + 1.02, y + 0.1, 2.9, 0.36, [n], size=12.5, bold=True, color=BLUE, anchor=MSO_ANCHOR.MIDDLE)
        tb(s, X0 + 3.85, y + 0.1, lw - 3.98, 0.36, [sc], size=9.5, color=GRAY, align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)
        tb(s, X0 + 0.18, y + 0.5, lw - 0.35, 0.55, [d], size=10.5, line=1.15)
    y = 5.05
    card(s, X0, y, lw, 1.15, fill=LBLUE, line="B9CDE6")
    tb(s, X0 + 0.18, y + 0.05, lw - 0.3, 1.05, [
        [("加载顺序（写入提示词的前置条件）", {"bold": True, "color": BLUE, "size": 11})],
        [("研判 / 生成工单：", {"bold": True}), ("evidence-citation → fund-chain-investigation", {})],
        [("版本比较：", {"bold": True}), ("evidence-citation → rule-update-rejudge", {})],
        [("查看已有工单：", {"bold": True}), ("evidence-citation → get_ticket，不调用 make_ticket", {})]],
       size=10, line=1.1, space_after=1, anchor=MSO_ANCHOR.MIDDLE)
    rx = X0 + lw + 0.25
    rw = X0 + W - rx
    p, pw, ph = picture(s, "img/run_skill.png", rx, 1.48, w=rw)
    for k, fy in enumerate([0.575, 0.915]):
        circle_num(s, rx + rw - 0.48, 1.48 + ph * fy - 0.15, 0.3, str(k + 1), fill=RED, size=10)
    tb(s, rx, 1.48 + ph + 0.08, rw, 6.2 - 1.48 - ph - 0.08, [
        [("平台实测（2026-10-31）：", {"bold": True}), ("用户要求查看 A0209 的 v1 已有工单。", {})],
        [("① 先用 read_skill_md 加载 evidence-citation；② 再调用 get_ticket 读取工单，全程未调用 make_ticket。", {})]],
       size=10, color=NAVY, line=1.15, space_after=2)
    notes(s, "三个 Skill：evidence-citation 管证据引用格式，fund-chain-investigation 编排单账户研判，rule-update-rejudge 管版本重判。"
             "它们只规范流程和输出，计算仍由 MCP 工具完成。右边是平台实测：查看已有工单时，智能体先加载证据技能，再调用 get_ticket，没有重新生成工单。")


def s_platform(s):
    title(s, "Nexent 平台配置：当前发布 v1.4，累计 11 个版本", "配置与版本信息于 2026-11-03 在平台页面核对")
    lw = 3.45
    card(s, X0, 1.48, lw, 4.72)
    section_label(s, X0 + 0.18, 1.55, lw - 0.3, "智能体配置", size=12.5)
    kv = [("模型", "DeepSeek-V4.1-Flash"), ("执行方式", "Python CodeAgent，每步一个工具调用"), ("工具", "7 个业务工具 + 知识库检索"),
          ("技能", "3 个 Skill"), ("知识库", "4 个，Qwen3-Embedding-4B"), ("运行策略", "最大 15 步，平台记忆关闭"),
          ("答复结构", "工具事实 / 规则定义与来源分区"), ("数据声明", "按 _demo 标记写明合成数据")]
    tb(s, X0 + 0.18, 1.9, lw - 0.3, 2.0, [[(a + "  ", {"bold": True, "color": BLUE}), (b, {})] for a, b in kv], size=10, line=1.08, space_after=2.5)
    section_label(s, X0 + 0.18, 3.95, lw - 0.3, "关键迭代", size=12.5)
    it = [("V5", "增加 Python 执行协议"), ("V8", "收紧输出格式"), ("V9", "单技能拆为三个技能"), ("v1.3", "接入规则新库与法规库"), ("v1.4", "监管检索改为分步进行")]
    for i, (a, b) in enumerate(it):
        yy = 4.32 + i * 0.36
        chip(s, X0 + 0.18, yy + 0.04, 0.55, 0.24, a, LBLUE if i < 4 else BLUE, BLUE if i < 4 else WHITE, size=8.5)
        tb(s, X0 + 0.85, yy, lw - 1.0, 0.32, [b], size=10, anchor=MSO_ANCHOR.MIDDLE)
    x1 = X0 + lw + 0.2
    _, w1, h1 = picture(s, "img/tools.png", x1, 1.48, h=3.9)
    tb(s, x1, 5.45, w1, 0.7, ["图 1：工具与技能页，当前发布版本 fundtrace-v1.4-监管检索分步-20261103，已选 fundtrace MCP 的 7 个工具"],
       size=9, color=GRAY, line=1.1)
    x2 = x1 + w1 + 0.2
    _, w2, h2 = picture(s, "img/versions.png", x2, 1.48, w=X0 + W - x2, h=3.9)
    tb(s, x2, 5.45, w2, 0.7, ["图 2：版本管理，每个版本附修改说明，可回溯 V1.1 至 v1.4 的调整原因"], size=9, color=GRAY, line=1.1)
    notes(s, "这是平台上的实际配置。左边是关键配置：DeepSeek-V4.1-Flash，Python CodeAgent 每步只调一个工具，最大 15 步，记忆关闭；"
             "下面是几次关键迭代。中间截图是工具与技能页，当前发布版本 v1.4；右边是版本管理，每个版本都写了修改原因，方便回溯。")


def s_ticket(s):
    title(s, "工单证据结构：支持证据、反向证据、缺失证据、建议动作四栏并列", "以平台实测 A0209 / v1 工单为例，编号可逐笔回查原始交易")
    card(s, X0, 1.45, W, 0.5, fill=LBLUE, line="B9CDE6")
    tb(s, X0 + 0.2, 1.45, W - 0.4, 0.5, [[("工单 TK-v1-A0209", {"bold": True, "color": BLUE}), ("   ｜  状态：", {"color": GRAY}),
                                         ("建议人工复核（REVIEW）", {"bold": True, "color": RED}), ("   ｜  角色：中转端   ｜  链：L-T01908   ｜  命中：R01、R04、R07、R08", {})]],
       size=11, anchor=MSO_ANCHOR.MIDDLE)
    _, pw, ph = picture(s, "img/run_ticket.png", X0, 2.1, h=4.1)
    rx = X0 + pw + 0.2
    rw = X0 + W - rx
    cw, chh = (rw - 0.12) / 2, 2.0
    cols = [("① 支持证据", "EVIDENCE", BLUE, LBLUE, [("5 笔交易，逐笔标注实际付款方与收款方", True),
                                                   ("T01932  A0283→A0209  70,850 元（首次对手）", False),
                                                   ("T01938  A0209→A0177  70,396 元", False),
                                                   ("T01908、T01913、T01942 为链上其他账户交易", False)]),
            ("② 反向证据", "COUNTER", TEAL, LTEAL, [("本工单为空", True), ("未命中 R09 工资、R10 商户经营", False),
                                                  ("为空不等于风险已排除，由人工结合材料判断", False)]),
            ("③ 缺失证据", "GAP", AMBER, LAMBER, [("GAP_KYC  对手方开户与实名信息", False), ("GAP_MEMO_DEVICE  附言与登录设备", False),
                                                ("GAP_CALLBACK  回访或报案记录", False), ("GAP_HISTORY  数据窗口外历史交易", False)]),
            ("④ 建议动作", "ACTION", RED, LRED, [("建议人工复核", True), ("由状态唯一决定：REVIEW → 建议人工复核", False),
                                               ("不作违法认定，不建议冻结或处罚", False)])]
    for i, (h, code, c, lc, items) in enumerate(cols):
        x = rx + (i % 2) * (cw + 0.12)
        y = 2.1 + (i // 2) * (chh + 0.1)
        card(s, x, y, cw, chh, fill=lc, line=None, alpha=95)
        tb(s, x + 0.14, y + 0.08, cw - 0.25, 0.32, [[(h, {"bold": True, "color": c, "size": 12}), (f"  {code}", {"size": 8.5, "color": c})]],
           anchor=MSO_ANCHOR.MIDDLE)
        tb(s, x + 0.14, y + 0.45, cw - 0.25, chh - 0.5,
           [dict(runs=[(t, {"bold": b})], bullet=not b, bucolor=c, after=3) for t, b in items], size=9.5, line=1.1)
    footnote(s, "截图：Nexent 平台只读查看 A0209 v1 工单（get_ticket，2026-10-31）。链上其他账户的交易须写明实际付款方和收款方，已由测试 test_ticket_evidence_direction 固化。")
    notes(s, "工单把证据结构完整摆出来。这是平台上 A0209 的 v1 工单：状态建议人工复核，角色中转端，链 L-T01908，命中四条规则。"
             "支持证据 5 笔，其中两笔直接涉及 A0209，另外三笔是链上其他账户之间的交易，工单逐笔写明实际付款方和收款方；"
             "反向证据为空；缺失证据列出四项，比如对手方实名信息、回访记录；建议动作只有建议人工复核，不做违法认定，也不建议冻结。")


def s_kb(s):
    title(s, "知识库检索：仿真规则、公开案例与监管原文分库管理", "规则库解释本系统口径，监管库与法规库按条引用原文，二者相互独立")
    lw = 5.95
    _, pw, ph = picture(s, "img/kb_list.png", X0, 1.48, w=lw)
    tb(s, X0, 1.48 + ph + 0.03, lw, 0.28, ["截图：知识库页面（显示其中两个库），均使用 Qwen3-Embedding-4B 向量化"], size=9, color=GRAY)
    rows = [("涉诈规则库", "仿真规则 v1、v2 条件及版本差异，由规则 YAML 生成", "3 / 7"),
            ("涉诈案例库", "5 篇公开案例摘要，逐篇注明来源链接与访问日期", "5 / 5"),
            ("涉诈规则新库", "银发〔2016〕261号通知及附件1、可疑交易报告办法第十一至十五条原文", "41 / 41"),
            ("涉诈法规库", "《反电信网络诈骗法》第十五至二十条等 10 条原文", "10 / 10")]
    ty = 1.48 + ph + 0.4
    table(s, X0, ty, lw, [1.25, 3.7, 1.0], [[[(a, {"bold": True, "color": BLUE})], b, c] for a, b, c in rows],
          ["知识库", "内容", "文档/分块"], size=9.5, row_h=0.47)
    rx = X0 + lw + 0.25
    rw = X0 + W - rx
    _, pw2, ph2 = picture(s, "img/run_reg.png", rx, 1.48, h=3.85)
    tb(s, rx, 1.48 + ph2 + 0.06, rw, 6.2 - 1.48 - ph2 - 0.06, [
        [("监管问答实测（检索测试智能体，2026-11-02）：", {"bold": True}),
         ("问“发现账户疑似涉诈，银行依法可以采取哪些措施？”，同时检索法规库与规则新库，答复引用反电诈法第十八条第三款列出四项防范措施，并说明可疑特征不能单独作为认定依据。", {})]],
       size=10, line=1.15)
    footnote(s, "检索测试集 50 题；首轮 10 题中 6 题通过，替换法规原文并调整提示词后 3 题复测通过；v1.4 主智能体改为先检索规则新库、再检索法规库。")
    notes(s, "知识库分四个：涉诈规则库解释本系统的仿真规则，案例库是带出处的公开报道摘要，规则新库和法规库是监管文件和反电诈法的逐字原文，按条切分。"
             "右边是监管问答的实测：问银行发现疑似涉诈账户可以采取哪些措施，答复引用反电诈法第十八条第三款，列出核实交易、重新核验身份、延迟结算、限制业务四项，"
             "并提示可疑特征不能单独认定涉诈。监管文件里的数字不当作本系统阈值。")


def s_metrics(s):
    title(s, "版本指标对比：v2 时间窗放宽后召回提升，干扰账户误报保持为零", "数据集 sim-gen_profile_v1-seed42，数字引自 eval/result.md")
    rows = [("埋入链识别（共 12 条）", "10 / 12", "12 / 12", "+2"), ("链边召回（共 57 条边）", "52 / 57", "57 / 57", "+5"),
            ("链边精确", "52 / 52", "57 / 59", "−2 条多识别边"), ("目标账户召回（共 18 个）", "16 / 18", "18 / 18", "+2"),
            ("干扰账户误报（共 63 个）", "0 / 63", "0 / 63", "持平"), ("背景账户告警", "2", "2", "持平")]
    rws = [[a, b, [(c, {"bold": True, "color": RED if d.startswith("+") else NAVY})], d] for a, b, c, d in rows]
    lw = 6.75
    table(s, X0, 1.48, lw, [2.6, 1.2, 1.2, 1.75], rws, ["评测指标", "v1（60 分钟）", "v2（120 分钟）", "变化"], size=10, row_h=0.42,
          aligns=[PP_ALIGN.LEFT, PP_ALIGN.CENTER, PP_ALIGN.CENTER, PP_ALIGN.CENTER])
    bw = (lw - 0.2) / 2
    bases = [("基线 B1：单笔 ≥1 万元即告警", "目标账户召回 18/18，但 48 户进入人工复核，其中 2 户为干扰账户。单笔阈值能找全目标，复核负担和误报更高。"),
             ("基线 B2：不看时间窗与资金守恒的追链", "本数据集上链指标与 v2 相同，因此不宣称追链算法全面优于基线；两者差异需在更复杂的数据上检验。")]
    for i, (a, b) in enumerate(bases):
        x = X0 + i * (bw + 0.2)
        card(s, x, 4.6, bw, 1.6)
        tb(s, x + 0.18, 4.68, bw - 0.3, 1.45, [[(a, {"bold": True, "color": AMBER, "size": 12})], [(b, {"size": 11.5})]], line=1.25, space_after=6)
    rx = X0 + lw + 0.25
    rw = X0 + W - rx
    card(s, rx, 1.48, rw, 4.72)
    section_label(s, rx + 0.2, 1.55, rw - 0.4, "v1 与 v2 主要比率（%）", size=12.5)
    cd = CategoryChartData()
    cd.categories = ["埋入链识别", "链边召回", "链边精确", "目标账户召回"]
    cd.add_series("v1", (83.3, 91.2, 100.0, 88.9))
    cd.add_series("v2", (100.0, 100.0, 96.6, 100.0))
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(rx + 0.1), Inches(1.95), Inches(rw - 0.2), Inches(4.15), cd)
    ch = gf.chart
    chart_style(ch)
    ch.has_legend = True
    ch.legend.position = XL_LEGEND_POSITION.TOP
    ch.legend.include_in_layout = False
    ch.legend.font.size = Pt(10)
    pl = ch.plots[0]
    pl.gap_width = 60
    pl.overlap = -10
    pl.has_data_labels = True
    pl.data_labels.number_format = "0.0"
    pl.data_labels.number_format_is_linked = False
    pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
    pl.data_labels.font.size = Pt(9)
    pl.data_labels.font.color.rgb = rgb(NAVY)
    for ser, c in zip(pl.series, ["9DB8D9", BLUE]):
        ser.format.fill.solid(); ser.format.fill.fore_color.rgb = rgb(c)
    va = ch.value_axis
    va.minimum_scale, va.maximum_scale = 0, 110
    va.visible = False
    va.has_major_gridlines = False
    ch.category_axis.format.line.color.rgb = rgb(LINE)
    ch.category_axis.tick_labels.font.size = Pt(10)
    ch.category_axis.tick_labels.font.color.rgb = rgb(NAVY)
    footnote(s, "注：v2 系统共识别 13 条链（含 1 条合租转发链），“识别埋入链数”与“系统识别链总数”口径不同；埋入链识别比率按 10/12、12/12 换算。")
    notes(s, "评测只在本数据集本口径下报告。时间窗从 60 分钟放宽到 120 分钟后，埋入链识别从 10/12 提到 12/12，链边召回和目标账户召回都到 100%，"
             "63 个干扰账户误报仍为零；代价是链边精确从 100% 降到 96.6%，多出的两条边来自合租转发。"
             "基线 B1 也能找全目标账户，但要人工复核 48 户；B2 在这个数据上和 v2 一样，所以不说全面优于基线。")


def s_rejudge(s):
    title(s, "规则版本重判：v1→v2 共 8 个账户状态变化，全部为升级", "同一批合成账户分别按两个规则版本判定，只列出状态发生变化的账户")
    lw = 7.0
    ks = [("300", "覆盖账户", NAVY), ("8", "状态变化", BLUE), ("8", "风险升级", RED), ("0", "风险降级", TEAL)]
    kw = (lw - 0.3) / 4
    for i, (n, l, c) in enumerate(ks):
        kpi(s, X0 + i * (kw + 0.1), 1.48, kw, 0.66, n, l, color=c, num_w=0.75, num_size=19, label_size=10.5)
    rows = [("A0015", "未见异常 → 存在风险信号", "疑似受骗付款端", "L-T01338", "—"),
            ("A0039", "存在风险信号 → 建议人工复核", "一级收款端", "L-T00197", "R01"),
            ("A0104", "未见异常 → 证据不足", "一级收款端", "L-T01454", "R01"),
            ("A0127", "未见异常 → 存在风险信号", "疑似受骗付款端", "L-T01454", "—"),
            ("A0146", "未见异常 → 存在风险信号", "疑似受骗付款端", "L-T01338", "—"),
            ("A0168", "未见异常 → 存在风险信号", "末端", "L-T01454", "—"),
            ("A0176", "存在风险信号 → 建议人工复核", "一级收款端", "L-T01338", "R01、R11"),
            ("A0261", "未见异常 → 存在风险信号", "疑似受骗付款端", "L-T00197", "—")]
    rws = [[[(a, {"bold": True, "color": BLUE})], [(b, {"bold": "人工复核" in b, "color": RED if "人工复核" in b else NAVY})], c, d, e]
           for a, b, c, d, e in rows]
    table(s, X0, 2.3, lw, [0.75, 2.45, 1.4, 1.1, 1.0], rws, ["账户", "状态变化", "v2 角色", "v2 链", "新增规则"], size=9.5, row_h=0.4)
    rx = X0 + lw + 0.25
    rw = X0 + W - rx
    card(s, rx, 1.48, rw, 2.95)
    section_label(s, rx + 0.18, 1.53, rw - 0.3, "典型案例：A0176 在 v2 成为一级收款端", size=12)
    draw_chain(s, rx + 0.55, 2.08, rw - 1.1, 1.1,
               {"A0015": (0.0, 0.1, "疑似受骗付款端"), "A0146": (0.0, 0.9, "疑似受骗付款端"), "A0176": (0.52, 0.5, "一级收款端"),
                "A0082": (1.0, 0.5, "末端")},
               [("A0015", "A0176", "39,044 元 · 10:26"), ("A0146", "A0176", "46,061 元 · 10:18"), ("A0176", "A0082", "82,445 元 · 11:37")], d=0.5)
    tb(s, rx + 0.18, 3.62, rw - 0.32, 0.8,
       ["最后一笔汇入 10:26，转出 11:37，间隔 71 分钟：超出 v1 的 60 分钟时间窗，落在 v2 的 120 分钟时间窗内；同时新命中 R11，状态升为“建议人工复核”。"],
       size=9.5, line=1.15)
    card(s, rx, 4.55, rw, 1.65)
    tb(s, rx + 0.18, 4.6, rw - 0.3, 1.55, [
        [("变化来源", {"bold": True, "color": BLUE, "size": 11.5})],
        dict(runs=[("R01 时间窗 60→120 分钟：新成 L-T00197、L-T01338、L-T01454 三条链", {})], bullet=True, after=2),
        dict(runs=[("v2 新增 R11：A0176 新命中", {})], bullet=True, after=2),
        dict(runs=[("迁移：未见异常→存在风险信号 5 户，存在风险信号→建议人工复核 2 户，未见异常→证据不足 1 户", {})], bullet=True, after=0)],
       size=9.5, line=1.12, space_after=2)
    footnote(s, "口径：同一批合成账户在两种规则口径下重算，变化来自规则调整，不是账户行为随时间变化；名单以 rejudge 返回为准。")
    notes(s, "把 v1 和 v2 对同一批 300 个账户各判一遍，有 8 个账户状态变化，全部是升级，没有降级。左边是完整名单。原因主要是时间窗放宽后新成了三条链，"
             "比如 A0176：最后一笔汇入 10:26，转出 11:37，相隔 71 分钟，v1 不成链，v2 成链，再加上新命中 R11，升为建议人工复核。"
             "要强调这是同一批账户在两种规则下的重算，不是账户行为变了。")


def s_verify(s):
    title(s, "端到端验证：平台答复与本地计算逐份比对", "测试针对 V9 正式版及其恢复副本；v1.3、v1.4 另做关键题回归")
    ks = [("51 份", "V9 发布前 15 次回归，业务 JSON 与本地计算一致", BLUE), ("14 / 15", "严格格式自动检查无告警，1 条人工复核保留", TEAL),
          ("19 份", "V9 发布后 7 次请求，业务返回全部一致", BLUE), ("22 份", "同租户恢复副本 10 次请求，全部一致", BLUE)]
    kw = (W - 0.6) / 4
    for i, (n, l, c) in enumerate(ks):
        kpi(s, X0 + i * (kw + 0.2), 1.48, kw, 0.82, n, l, color=c, num_w=1.2, num_size=19, label_size=10)
    rows = [("V9 发布前回归", "5 道演示题各 3 轮", "业务返回全部一致；14 次无告警，1 条告警人工复核后保留"),
            ("V9 发布后复测", "5 题 + 只读工单、不存在账户", "全部一致"),
            ("配置导出后恢复", "同租户导入副本，10 次请求", "全部一致；1 次正文遗漏，同题复测 2 次完整"),
            ("监管检索测试", "检索测试智能体，10 题", "首轮 6 题通过；调整后 3 题复测通过"),
            ("v1.3、v1.4 回归", "A0209 研判、A0105 反向证据等 4 题", "各 1 次，均通过")]
    lw = 7.2
    table(s, X0, 2.5, lw, [1.6, 2.4, 3.2], [[[(a, {"bold": True})], b, c] for a, b, c in rows], ["测试组", "规模", "结果"], size=9.5, row_h=0.55)
    rx = X0 + lw + 0.25
    rw = X0 + W - rx
    card(s, rx, 2.5, rw, 2.75)
    tb(s, rx + 0.18, 2.58, rw - 0.3, 2.6, [
        [("核对方法", {"bold": True, "color": BLUE, "size": 11.5})],
        dict(runs=[("工具实际调用顺序与返回字段", {})], bullet=True, after=1),
        dict(runs=[("交易方向、实际付款方与收款方", {})], bullet=True, after=1),
        dict(runs=[("check_ids.py 回查账户号、交易号、链编号", {})], bullet=True, after=1),
        dict(runs=[("正文完整性，“已完成”提示不作为通过条件", {})], bullet=True, after=6),
        [("发现的问题（如实保留）", {"bold": True, "color": AMBER, "size": 11.5})],
        dict(runs=[("恢复测试 1 次只读工单正文遗漏", {})], bullet=True, bucolor=AMBER, after=1),
        dict(runs=[("严格格式检查 1 条分区告警，人工复核后保留", {})], bullet=True, bucolor=AMBER, after=1),
        dict(runs=[("10-31 只读工单曾把链上其他账户交易误归属 A0209，已修正工单描述并补充测试", {})], bullet=True, bucolor=AMBER, after=0)],
       size=10, line=1.12, space_after=2)
    footnote(s, "说明：各组测试样本不同，不合并为“总成功率”；平台评估分 0.88、0.924 分别对应 V5、V8，不是 V9 分数。")
    notes(s, "端到端验证是把平台答复和本地算法结果逐份比对。V9 发布前五题各跑三轮，51 份业务 JSON 全部一致，14 次无自动告警；发布后 7 次、恢复副本 10 次也都一致。"
             "v1.3、v1.4 各做了关键题回归。右边是核对方法和发现的问题，比如恢复测试有一次正文遗漏、早期只读工单把其他账户交易误归属到 A0209，后者已经修复并加了测试。"
             "各组样本不同，不合并成总成功率。")


def s_bound(s):
    title(s, "成果边界与后续规划：已验证与待验证分开列示", "下一步在合规数据环境继续评测")
    cw = (W - 0.2) / 2
    cols = [("已在本仿真场景验证", TEAL, LTEAL, ["合成数据上的链路追踪与规则引擎，pytest 87 项通过", "MCP 工具 real 模式调用，云端 systemd 常驻",
                                             "三个 Skill 按意图加载与流程编排", "四个知识库检索，监管原文按条引用", "证据工单四栏结构与编号回查",
                                             "v1 / v2 规则重判与差异说明", "同租户配置导出与恢复，10 次请求结果一致"]),
            ("局限 / 尚未验证", AMBER, LAMBER, ["单一随机种子、7 天数据，阈值为仿真设定", "基线 B2 与 v2 指标相同，未宣称全面领先",
                                           "平台回归问法和次数有限，曾出现正文遗漏与格式偏差", "配置包仅完成同租户恢复，跨租户迁移未验证",
                                           "未接入真实数据；2025 年修订版报告办法尚未入库", "案例库为公开报道摘要，无逐笔流水，不作账户证据"])]
    for i, (h, c, lc, items) in enumerate(cols):
        x = X0 + i * (cw + 0.2)
        card(s, x, 1.48, cw, 3.1, fill=lc, line=None, alpha=92)
        tb(s, x + 0.25, 1.58, cw - 0.4, 0.36, [h], size=14, bold=True, color=c, anchor=MSO_ANCHOR.MIDDLE)
        tb(s, x + 0.25, 2.02, cw - 0.45, 2.75, [dict(runs=[(t, {})], bullet=True, bucolor=c, after=5) for t in items], size=11.5, line=1.15)
    section_label(s, X0, 4.85, W, "后续规划", size=13)
    st = [("近期", "补齐 v1.4 截图与演示视频，与终稿逐项核对"), ("中期", "多随机种子与参数扰动评测，扩大平台回归问法"),
          ("后续", "在获授权的合规数据环境评测，开展跨场景迁移")]
    sw = (W - 0.4) / 3
    for i, (a, b) in enumerate(st):
        x = X0 + i * (sw + 0.2)
        box(s, x, 5.25, sw, 0.85, fill=BLUE if i == 0 else LBLUE, line=None, shape=MSO_SHAPE.CHEVRON if i else MSO_SHAPE.PENTAGON)
        tb(s, x + 0.35, 5.25, sw - 0.7, 0.85, [[(a + "  ", {"bold": True, "size": 12}), (b, {"size": 11})]],
           color=WHITE if i == 0 else NAVY, anchor=MSO_ANCHOR.MIDDLE, line=1.1)
    notes(s, "最后把已验证和没验证的分开。已验证的是合成数据上的算法、MCP 调用、Skill 编排、四个知识库检索、工单结构和规则重判；"
             "局限是单一种子、仿真阈值、平台回归次数有限、跨租户迁移和真实数据都没验证。下一步先补齐截图和视频，再做多种子评测，"
             "最后在获得授权的合规数据环境里评测。")


BUILDERS = [s_pain, s_idea, s_system, s_data, s_trace, s_rules, s_mcp, s_skills, s_platform, s_ticket, s_kb, s_metrics,
            s_rejudge, s_verify, s_bound]


def main(src, dst):
    prs = Presentation(src)
    ids = list(prs.slides._sldIdLst)
    # 原第 2–14 页复用为内容页框架，新增的第 16、17 页插入为“平台配置”“知识库检索”
    order = [1, 2, 3, 4, 5, 6, 7, 8, 9, 16, 10, 17, 11, 12, 13, 14, 15]
    lst = prs.slides._sldIdLst
    for el in ids:
        lst.remove(el)
    for k in order:
        lst.append(ids[k - 1])
    slides = list(prs.slides)
    for sl, fn in zip(slides[1:16], BUILDERS):
        clear(sl)
        fn(sl)
    prs.save(dst)
    print("saved", dst, len(slides))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
