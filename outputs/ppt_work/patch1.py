p = 'build_ppt.py'
s = open(p, encoding='utf-8').read()


def rep(a, b, cnt=1):
    global s
    assert s.count(a) == cnt, (s.count(a), a[:80])
    s = s.replace(a, b)


rep("""        para.space_after = Pt(opts.get("after", space_after))
""", """        para.space_after = Pt(opts.get("after", space_after))
        _pPr = para._p.get_or_add_pPr()
        _pPr.set("eaLnBrk", "1"); _pPr.set("hangingPunct", "1"); _pPr.set("latinLnBrk", "0")
""")

rep("""# ---------------------------------------------------------------- 各页内容""", """ROLE = {"疑似受骗付款端": ("EAB8BC", "B5545C"), "一级收款端": ("F4C47E", "B07A1F"), "中转端": ("F1DF7C", "A08A1E"),
        "末端": ("B9DBAC", "4E8A3E")}


def draw_chain(slide, x, y, w, h, nodes, edges, d=0.5):
    pos = {}
    for k, (rx, ry, role) in nodes.items():
        cx, cy = x + rx * w, y + ry * h
        pos[k] = (cx, cy)
        fc, lc = ROLE[role]
        c = circle_num(slide, cx - d / 2, cy - d / 2, d, k, fill=fc, color=NAVY, size=8.5)
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
        tb(slide, mx - 0.62, my - 0.27, 1.24, 0.22, [lab], size=8.5, color=NAVY, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


# ---------------------------------------------------------------- 各页内容""")

rep('section_label(s, px + 0.2, y + 0.15, pw - 0.4, "链路研判：Nexent 智能体 + FundTrace MCP")',
    'section_label(s, px + 0.2, y + 0.15, pw - 0.4, "链路研判：智能体 + MCP 工具")')
rep("""    tb(s, ox + 0.2, y + 0.65, ow - 0.35, 2.9, [dict(runs=[(t, {})], bullet=True, bucolor=TEAL, after=9) for t in outs], size=11.5)""",
    """    tb(s, ox + 0.2, y + 0.62, ow - 0.35, 2.0, [dict(runs=[(t, {})], bullet=True, bucolor=TEAL, after=5) for t in outs], size=11.5)
    box(s, ox + 0.2, y + 2.6, ow - 0.4, 0.98, fill=WHITE, line="B5DAD4", alpha=90)
    tb(s, ox + 0.32, y + 2.62, ow - 0.6, 0.94, [[("示例（A0209 / v1）", {"bold": True, "color": TEAL, "size": 10})],
                                              [("链 L-T01908 · 中转端 · 命中 4 条规则", {"size": 10})],
                                              [("状态：建议人工复核", {"size": 10, "bold": True, "color": RED})]],
       line=1.05, space_after=1, anchor=MSO_ANCHOR.MIDDLE)""")

rep('''        ("01", "数据与规范", ["300 账户、2,973 笔交易、12 条埋入链，SHA256 冻结", "数据、规则、判定与输出三份规范及 JSON Schema", "规则 YAML v1 / v2，阈值为仿真设定"], "data/ · Data and Rules/"),
        ("02", "算法与 MCP", ["trace：时序 + 资金守恒追链", "R01–R11 规则引擎、工单判定、版本重判", "FastMCP 服务 8 个工具，real 模式，systemd 常驻"], "core/ · mcp_server/"),
        ("03", "Nexent 智能体", ["当前发布 fundtrace-v1.4（平台第 11 版）", "DeepSeek-V4.1-Flash，最大 15 步", "7 个业务工具 + 3 个 Skill 按意图编排"], "agent/"),
        ("04", "知识库与评测", ["4 个知识库共 59 份文档（3 + 5 + 41 + 10）", "离线评测、基线 B1/B2、链路图", "pytest 87 项通过（2026-11-03）"], "kb/ · eval/ · tests/"),''',
    '''        ("01", "数据与规范", ["300 账户、2,973 笔交易、12 条埋入链，SHA256 冻结", "数据、规则、判定与输出三份规范及 JSON Schema", "规则 YAML v1 / v2，阈值为仿真设定", "标注答案与工具代码隔离，泄题检查自动执行"], "data/ · Data and Rules/"),
        ("02", "算法与 MCP", ["trace：时序 + 资金守恒追链", "R01–R11 规则引擎、工单判定、版本重判", "FastMCP 服务 8 个工具，real 模式", "云端 systemd 常驻，自检 19 次调用通过"], "core/ · mcp_server/"),
        ("03", "Nexent 智能体", ["当前发布 fundtrace-v1.4（平台第 11 版）", "DeepSeek-V4.1-Flash，最大 15 步", "7 个业务工具 + 3 个 Skill 按意图编排", "答复分“工具事实”与“规则定义与来源”两区"], "agent/"),
        ("04", "知识库与评测", ["4 个知识库共 59 份文档（3 + 5 + 41 + 10）", "离线评测、基线 B1 / B2、链路图", "pytest 87 项全部通过", "检索测试集 50 题，答复编号回查脚本"], "kb/ · eval/ · tests/"),''')
rep('''        tb(s, x + 0.2, y + 1.15, cw - 0.35, 2.2, [dict(runs=[(t, {})], bullet=True, after=8) for t in items], size=11, line=1.2)''',
    '''        tb(s, x + 0.2, y + 1.12, cw - 0.35, 2.4, [dict(runs=[(t, {})], bullet=True, after=6) for t in items], size=11, line=1.15)''')

rep('''    k = [("300", "合成账户\\n个人 250 · 商户 30 · 企业 20", BLUE), ("2,973", "合成交易流水\\n分钟级时间戳", BLUE),
         ("12", "埋入涉诈资金链\\n受骗转出 2.5–5 万元/笔", RED), ("7 天", "2026-03-01 至 03-07\\nAsia/Shanghai", TEAL)]
    kw = (W - 0.6) / 4
    for i, (n, l, c) in enumerate(k):
        kpi(s, X0 + i * (kw + 0.2), 1.5, kw, 0.82, n, l, color=c, num_w=1.15, num_size=21, label_size=10)''',
    '''    k = [("300", "合成账户\\n个人 250 · 商户 30 · 企业 20", BLUE, 0.78), ("2,973", "合成交易流水\\n分钟级时间戳", BLUE, 1.12),
         ("12", "埋入涉诈资金链\\n单笔受骗 2.5–5 万元", RED, 0.55), ("7 天", "2026-03-01 至 03-07\\nAsia/Shanghai", TEAL, 0.92)]
    kw = (W - 0.6) / 4
    for i, (n, l, c, nw) in enumerate(k):
        kpi(s, X0 + i * (kw + 0.2), 1.5, kw, 0.82, n, l, color=c, num_w=nw, num_size=21, label_size=10)''')
rep('''    ch = gf.chart
    chart_style(ch)
    ch.has_legend = False
    pl = ch.plots[0]
    pl.gap_width = 45''', '''    ch = gf.chart
    chart_style(ch)
    ch.has_title = False
    ch.has_legend = False
    pl = ch.plots[0]
    pl.gap_width = 45''')

rep('''    _, pw, ph = picture(s, "img/chain_v1.png", rx + 0.15, 1.95, w=rw - 0.3, border=False)
    ty = 1.95 + ph + 0.05''', '''    draw_chain(s, rx + 0.45, 2.0, rw - 0.9, 1.45,
               {"A0044": (0.0, 0.12, "疑似受骗付款端"), "A0287": (0.0, 0.88, "疑似受骗付款端"), "A0283": (0.3, 0.5, "一级收款端"),
                "A0209": (0.55, 0.5, "中转端"), "A0177": (0.78, 0.5, "中转端"), "A0186": (1.0, 0.5, "末端")},
               [("A0044", "A0283", "35,710 元 · 14:28"), ("A0287", "A0283", "36,059 元 · 14:33"), ("A0283", "A0209", "70,850 元 · 15:04"),
                ("A0209", "A0177", "70,396 元 · 15:14"), ("A0177", "A0186", "70,093 元 · 15:20")])
    ty = 3.75''')

rep('''["编号", "名称", "类型", "关键条件（v1 参数）"], size=9.5, row_h=0.32)''', '''["编号", "名称", "类型", "关键条件（v1 参数）"], size=9.5, row_h=0.295)''')

rep('''           "画像 → 流水 → 追链 → 规则 → 检索 → 工单 → 核对，任一步失败即停止，不补造结果"),''',
    '''           "画像 → 流水 → 追链 → 规则 → 检索 → 工单 → 核对，任一步失败即停止，不补造结果；答复按结论、支持、反向、缺失证据与规则依据五项组织"),''')
rep('''           "先 rejudge 再检索规则差异，列出全部变化账户；用户指定账户后才生成新版本工单")]''',
    '''           "先 rejudge 再检索规则差异，列出全部变化账户；用户指定账户后才生成新版本工单；说明变化来自规则口径调整")]''')

rep('''          ("技能", "3 个 Skill"), ("知识库", "4 个，Qwen3-Embedding-4B"), ("运行策略", "最大 15 步，平台记忆关闭")]''',
    '''          ("技能", "3 个 Skill"), ("知识库", "4 个，Qwen3-Embedding-4B"), ("运行策略", "最大 15 步，平台记忆关闭"),
          ("答复结构", "工具事实 / 规则定义与来源分区"), ("数据声明", "按 _demo 标记写明合成数据")]''')
rep('''    tb(s, X0 + 0.18, 1.92, lw - 0.3, 2.0, [[(a + "  ", {"bold": True, "color": BLUE}), (b, {})] for a, b in kv], size=10, line=1.1, space_after=4)''',
    '''    tb(s, X0 + 0.18, 1.9, lw - 0.3, 2.0, [[(a + "  ", {"bold": True, "color": BLUE}), (b, {})] for a, b in kv], size=10, line=1.08, space_after=2.5)''')

rep('''["评测指标", "v1（60 分钟窗）", "v2（120 分钟窗）", "变化"]''', '''["评测指标", "v1（60 分钟）", "v2（120 分钟）", "变化"]''')
rep('''    bases = [("基线 B1：单笔 ≥1 万元即告警", "目标账户召回 18/18，但 48 户进入人工复核，其中 2 户为干扰账户"),
             ("基线 B2：不看时间窗与资金守恒的追链", "本数据集上链指标与 v2 相同，因此不宣称追链算法全面优于基线")]''',
    '''    bases = [("基线 B1：单笔 ≥1 万元即告警", "目标账户召回 18/18，但 48 户进入人工复核，其中 2 户为干扰账户。单笔阈值能找全目标，复核负担和误报更高。"),
             ("基线 B2：不看时间窗与资金守恒的追链", "本数据集上链指标与 v2 相同，因此不宣称追链算法全面优于基线；两者差异需在更复杂的数据上检验。")]''')

rep('''    _, pw, ph = picture(s, "img/chain_v2.png", rx + 0.12, 1.9, w=rw - 0.24, border=False)
    tb(s, rx + 0.18, 1.9 + ph + 0.04, rw - 0.32, 4.4 - 1.9 - ph - 0.04,''', '''    draw_chain(s, rx + 0.5, 2.05, rw - 1.0, 1.2,
               {"A0015": (0.0, 0.1, "疑似受骗付款端"), "A0146": (0.0, 0.9, "疑似受骗付款端"), "A0176": (0.52, 0.5, "一级收款端"),
                "A0082": (1.0, 0.5, "末端")},
               [("A0015", "A0176", "39,044 元 · 10:26"), ("A0146", "A0176", "46,061 元 · 10:18"), ("A0176", "A0082", "82,445 元 · 11:37")], d=0.46)
    tb(s, rx + 0.18, 3.5, rw - 0.32, 0.9,''')

rep('''        dict(runs=[("恢复测试 1 次只读工单正文遗漏", {})], bullet=True, bucolor=AMBER, after=1),''',
    '''        dict(runs=[("恢复测试 1 次只读工单正文遗漏", {})], bullet=True, bucolor=AMBER, after=1),
        dict(runs=[("严格格式检查 1 条分区告警，人工复核后保留", {})], bullet=True, bucolor=AMBER, after=1),''')

rep('''                                             "v1 / v2 规则重判与差异说明"]),''', '''                                             "v1 / v2 规则重判与差异说明", "同租户配置导出与恢复，10 次请求结果一致"]),''')
rep('''                                           "未接入真实数据；2025 年修订版报告办法尚未入库"])]''', '''                                           "未接入真实数据；2025 年修订版报告办法尚未入库", "案例库为公开报道摘要，无逐笔流水，不作账户证据"])]''')
open(p, 'w', encoding='utf-8').write(s)
print('patched')
