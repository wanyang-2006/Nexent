p = 'build_ppt.py'
s = open(p, encoding='utf-8').read()


def rep(a, b, cnt=1):
    global s
    assert s.count(a) == cnt, (s.count(a), a[:80])
    s = s.replace(a, b)


# 圆形节点文字不换行
rep("""    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    fill_tf(tf, [text], size=size, color=color, bold=True, align=PP_ALIGN.CENTER, space_after=0, line=1.0)
    return s


def arrow(""", """    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    fill_tf(tf, [text], size=size, color=color, bold=True, align=PP_ALIGN.CENTER, space_after=0, line=1.0)
    tf.word_wrap = False
    return s


def arrow(""")
# 链图：节点略大，边标签两行
rep("""def draw_chain(slide, x, y, w, h, nodes, edges, d=0.5):""", """def draw_chain(slide, x, y, w, h, nodes, edges, d=0.58):""")
rep("""        c = circle_num(slide, cx - d / 2, cy - d / 2, d, k, fill=fc, color=NAVY, size=8.5)""",
    """        c = circle_num(slide, cx - d / 2, cy - d / 2, d, k, fill=fc, color=NAVY, size=8)""")
rep("""        tb(slide, mx - 0.62, my - 0.27, 1.24, 0.22, [lab], size=8.5, color=NAVY, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)""",
    """        tb(slide, mx - 0.5, my - 0.4, 1.0, 0.36, lab.split(" · "), size=8, color=NAVY, align=PP_ALIGN.CENTER,
           anchor=MSO_ANCHOR.BOTTOM, line=1.0, space_after=0)""")
rep("""[("A0015", "A0176", "39,044 元 · 10:26"), ("A0146", "A0176", "46,061 元 · 10:18"), ("A0176", "A0082", "82,445 元 · 11:37")], d=0.46)""",
    """[("A0015", "A0176", "39,044 元 · 10:26"), ("A0146", "A0176", "46,061 元 · 10:18"), ("A0176", "A0082", "82,445 元 · 11:37")], d=0.5)""")
# 追链页：图区与下方文字位置
rep("""    draw_chain(s, rx + 0.45, 2.0, rw - 0.9, 1.45,""", """    draw_chain(s, rx + 0.55, 2.05, rw - 1.1, 1.5,""")
rep("""    ty = 3.75""", """    ty = 3.88""")
# 重判页：图与文字位置
rep("""    draw_chain(s, rx + 0.5, 2.05, rw - 1.0, 1.2,""", """    draw_chain(s, rx + 0.55, 2.08, rw - 1.1, 1.1,""")
rep("""    tb(s, rx + 0.18, 3.5, rw - 0.32, 0.9,""", """    tb(s, rx + 0.18, 3.62, rw - 0.32, 0.8,""")
# 指标页：基线卡片字号
rep("""[[(a, {"bold": True, "color": AMBER, "size": 11})], [(b, {"size": 10.5})]], line=1.2, space_after=5)""",
    """[[(a, {"bold": True, "color": AMBER, "size": 12})], [(b, {"size": 11.5})]], line=1.25, space_after=6)""")
# 边界页：卡片高度收紧并上移后续规划
rep("""        card(s, x, 1.48, cw, 3.35, fill=lc, line=None, alpha=92)""", """        card(s, x, 1.48, cw, 3.1, fill=lc, line=None, alpha=92)""")
rep("""    section_label(s, X0, 5.0, W, "后续规划", size=13)""", """    section_label(s, X0, 4.85, W, "后续规划", size=13)""")
rep("""        box(s, x, 5.38, sw, 0.8, fill=BLUE if i == 0 else LBLUE""", """        box(s, x, 5.25, sw, 0.85, fill=BLUE if i == 0 else LBLUE""")
rep("""        tb(s, x + 0.35, 5.38, sw - 0.7, 0.8, [[(a + "  ", {"bold": True, "size": 12}), (b, {"size": 10.5})]],""",
    """        tb(s, x + 0.35, 5.25, sw - 0.7, 0.85, [[(a + "  ", {"bold": True, "size": 12}), (b, {"size": 11})]],""")
# 验证页：右卡高度与表格对齐
rep("""    card(s, rx, 2.5, rw, 3.3)
    tb(s, rx + 0.18, 2.58, rw - 0.3, 3.15, [""", """    card(s, rx, 2.5, rw, 2.75)
    tb(s, rx + 0.18, 2.58, rw - 0.3, 2.6, [""")
open(p, 'w', encoding='utf-8').write(s)
print('patched')
