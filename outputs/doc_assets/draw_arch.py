import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

fig, ax = plt.subplots(figsize=(12, 8), dpi=200)
ax.set_xlim(0, 120); ax.set_ylim(0, 80); ax.axis("off")

C = {"user": ("#f2eaff", "#7854a6"), "agent": ("#e8f1ff", "#426b9a"),
     "svc": ("#e7f5ed", "#38845b"), "kb": ("#fff3d6", "#a77a16"), "data": ("#eef0f3", "#6b7280")}

def box(x, y, w, h, title, lines, kind, fs=10.5):
    fc, ec = C[kind]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.0",
                                fc=fc, ec=ec, lw=1.4))
    ax.text(x + w / 2, y + h - 3, title, ha="center", va="center", fontsize=fs + 1, weight="bold", color="#1f2937")
    for i, t in enumerate(lines):
        ax.text(x + w / 2, y + h - 7.2 - i * 3.4, t, ha="center", va="center", fontsize=fs - 1.5, color="#374151")

def arrow(x1, y1, x2, y2, text="", off=(0, 0)):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=13, lw=1.3, color="#4b5563"))
    if text:
        ax.text((x1 + x2) / 2 + off[0], (y1 + y2) / 2 + off[1], text, ha="center", va="center",
                fontsize=8.5, color="#374151", bbox=dict(fc="white", ec="none", pad=0.6))

box(1, 37, 17, 17, "使用者", ["分析人员提问", "账户研判 / 读工单", "版本比较 / 监管问答"], "user")
box(25, 31, 31, 24, "Nexent 智能体", ["涉诈资金链路研判助手", "DeepSeek-V4.1-Flash", "按意图加载 Skill", "按步骤调用工具", "事实与依据分区输出"], "agent")
box(25, 63, 31, 15, "3 个 Skill（流程与证据约束）", ["evidence-citation", "fund-chain-investigation", "rule-update-rejudge"], "agent", fs=10)
box(64, 56, 25, 21, "FundTrace MCP 服务", ["FastMCP · SSE · 端口 8900", "MCP_MODE=real", "7 个业务工具 + hello", "systemd 常驻"], "svc", fs=10)
box(95, 53, 24, 24, "core 算法层", ["store 数据装载", "trace 时序追链", "rules 规则 R01–R11", "ticket 判定与工单", "rejudge 版本重判"], "svc", fs=10)
box(95, 36, 24, 13, "合成数据与规则", ["300 账户 / 2973 笔交易", "rules_v1 / v2.yaml"], "data", fs=10)
ax.add_patch(FancyBboxPatch((64, 2), 55, 28, boxstyle="round,pad=0.3,rounding_size=1.0", fc=C["kb"][0], ec=C["kb"][1], lw=1.4))
ax.text(91.5, 26.5, "Nexent 知识库检索（knowledge_base_search）", ha="center", va="center", fontsize=11, weight="bold", color="#1f2937")
kbs = [("涉诈规则库", "仿真规则 v1/v2", "3 文档 / 7 分块"), ("涉诈案例库", "公开案例摘要", "5 文档 / 5 分块"),
       ("涉诈规则新库", "监管文件原文", "41 文档 / 41 分块"), ("涉诈法规库", "反电诈法原文", "10 文档 / 10 分块")]
for i, (n, d, c) in enumerate(kbs):
    x = 65.5 + i * 13.2
    ax.add_patch(FancyBboxPatch((x, 4.5), 12, 17, boxstyle="round,pad=0.3,rounding_size=0.8", fc="white", ec="#a77a16", lw=1))
    ax.text(x + 6, 17.5, n, ha="center", fontsize=9, weight="bold")
    ax.text(x + 6, 12.5, d, ha="center", fontsize=8, color="#374151")
    ax.text(x + 6, 8, c, ha="center", fontsize=7.6, color="#6b7280")
box(1, 4, 55, 15, "辅助研判答复", ["工具事实：账户、链路、交易证据、反向证据、缺失证据、工单", "规则定义与来源：知识库条文与平台引用标记"], "user", fs=10)

arrow(18.5, 45.5, 24.5, 45.5, "请求", off=(0, 2.2))
arrow(40.5, 55.5, 40.5, 62.5, "按意图加载", off=(6.5, 0))
arrow(56.5, 50, 63.5, 64, "工具调用", off=(-2.5, 2))
arrow(63.5, 59, 56.5, 45, "JSON 结果", off=(3.5, -2.5))
arrow(89.5, 66.5, 94.5, 66.5)
arrow(107, 49.5, 107, 52.5)
arrow(56.5, 36, 63.5, 24, "条文检索", off=(-3, -1))
arrow(36, 30.5, 30, 19.5)
arrow(9.5, 19.5, 9.5, 36.5)
fig.savefig("outputs/doc_assets/architecture.png", bbox_inches="tight", facecolor="white")
