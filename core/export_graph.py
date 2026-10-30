"""资金链路图导出：把 trace 的链画成 PNG，写到 eval/graphs/<版本>_<chain_id>.png。

用法（仓库根目录）：
  python -m core.export_graph                                   # 默认 4 张演示图
  python -m core.export_graph --version v1 --chains L-T01908    # 指定版本与链号
  python -m core.export_graph --version v2                      # 该版本全部链

只读 data/（经 core.trace），不读答案目录。只依赖 matplotlib，不依赖 networkx。
节点按 trace 的 roles 着色，横向位置为距源点的深度，边上标“金额 元 / HH:MM”，
同一对账户有多笔交易时分开弯曲绘制，避免重叠。
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch  # noqa: E402

from . import trace  # noqa: E402
from .ruleset import ROOT, norm_version  # noqa: E402
from .store import get_store  # noqa: E402

OUT_DIR = ROOT / "eval" / "graphs"
DEFAULT_JOBS = [("v1", "L-T01908"), ("v1", "L-T01001"), ("v2", "L-T01338"), ("v2", "L-T01454")]

ROLE_COLOR = {
    "疑似受骗付款端": "#E8B4B8",
    "一级收款端": "#F4C27A",
    "中转端": "#F2E27A",
    "拆分端": "#9FC9E8",
    "末端": "#B5D8A8",
}
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False


def _depth(chain: dict) -> dict:
    """账户深度：从没有入边的账户出发做 BFS（与 trace 的排序口径一致）。"""
    recv, indeg = defaultdict(set), defaultdict(int)
    for e in chain["edges"]:
        recv[e["from_acct"]].add(e["to_acct"])
        indeg[e["to_acct"]] += 1
    depth = {a: 0 for a in chain["accounts"] if indeg[a] == 0}
    frontier = sorted(depth)
    while frontier:
        nxt = []
        for a in frontier:
            for b in sorted(recv[a]):
                if b not in depth:
                    depth[b] = depth[a] + 1
                    nxt.append(b)
        frontier = nxt
    return depth


def _layout(chain: dict) -> dict:
    depth = _depth(chain)
    cols = defaultdict(list)
    for a in chain["accounts"]:
        cols[depth.get(a, 0)].append(a)
    pos = {}
    for d, accs in cols.items():
        accs = sorted(accs)
        n = len(accs)
        for i, a in enumerate(accs):
            pos[a] = (d * 3.6, (n - 1) / 2 - i)
    return pos


def draw_chain(chain: dict, version: str, out: Path) -> None:
    pos = _layout(chain)
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    w = max(8.0, (max(xs) - min(xs)) * 1.0 + 4.5)
    h = max(4.5, (max(ys) - min(ys)) * 0.85 + 3.2)
    fig, ax = plt.subplots(figsize=(min(w, 24), min(h, 20)), dpi=150)
    ax.set_axis_off()

    pair_seen = defaultdict(int)
    pair_total = defaultdict(int)
    for e in chain["edges"]:
        pair_total[(e["from_acct"], e["to_acct"])] += 1
    for e in chain["edges"]:
        a, b = e["from_acct"], e["to_acct"]
        k = pair_seen[(a, b)]
        pair_seen[(a, b)] += 1
        rad = 0.0 if pair_total[(a, b)] == 1 else (k - (pair_total[(a, b)] - 1) / 2) * 0.25
        (x1, y1), (x2, y2) = pos[a], pos[b]
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), connectionstyle=f"arc3,rad={rad}",
                                     arrowstyle="-|>", mutation_scale=14, lw=1.2, color="#555555",
                                     shrinkA=24, shrinkB=24, zorder=1))
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        # 弯曲边的标注沿法线方向偏移，近似落在弧线上
        dx, dy = x2 - x1, y2 - y1
        norm = (dx * dx + dy * dy) ** 0.5 or 1.0
        mx += -dy / norm * rad * norm * 0.5
        my += dx / norm * rad * norm * 0.5
        ax.annotate(f"{e['amount']} 元 / {e['time'][-5:]}", (mx, my), xytext=(0, 5),
                    textcoords="offset points", ha="center", va="bottom", fontsize=7,
                    color="#222222", zorder=3,
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))

    for a, (x, y) in pos.items():
        role = chain["roles"].get(a, "")
        ax.scatter([x], [y], s=2200, c=ROLE_COLOR.get(role, "#DDDDDD"), edgecolors="#333333",
                   linewidths=1.0, zorder=2)
        ax.annotate(a, (x, y), ha="center", va="center", fontsize=8, fontweight="bold", zorder=4)
        ax.annotate(role, (x, y), xytext=(0, -26), textcoords="offset points", ha="center",
                    va="top", fontsize=6.5, color="#333333", zorder=4)

    handles = [plt.Line2D([0], [0], marker="o", ls="", ms=9, mfc=c, mec="#333333", label=r)
               for r, c in ROLE_COLOR.items() if r in chain["roles"].values()]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.0, 1.0), fontsize=8, frameon=False,
              title="账户角色", title_fontsize=8)
    ax.set_title(f"资金链 {chain['chain_id']}（规则 {version}）  "
                 f"{chain['hops']} 跳 · 首段合计 {chain['total_amount']} 元 · 历时 {chain['duration_minutes']} 分钟\n"
                 "合成数据，仅在本作品设定的仿真场景内有效；辅助研判，不构成定性结论", fontsize=10)
    ax.margins(0.12)
    lo, hi = min(ys), max(ys)
    if hi - lo < 2:                       # 全在一条水平线上时，给纵轴一个最小范围
        mid = (lo + hi) / 2
        ax.set_ylim(mid - 1.2, mid + 1.2)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.88, bottom=0.04)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="导出资金链路图")
    ap.add_argument("--version", help="规则版本；不给则导出默认 4 张演示图")
    ap.add_argument("--chains", nargs="*", help="链号；不给则导出该版本全部链")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    a = ap.parse_args(argv)
    st = get_store()
    jobs = []
    if a.version:
        v = norm_version(a.version) or a.version
        ids = a.chains or [c["chain_id"] for c in trace.all_chains(st, v)]
        jobs = [(v, cid) for cid in ids]
    else:
        jobs = DEFAULT_JOBS
    code = 0
    for v, cid in jobs:
        chain = next((c for c in trace.all_chains(st, v) if c["chain_id"] == cid), None)
        if chain is None:
            print(f"[跳过] {v} 下没有链 {cid}")
            code = 1
            continue
        out = a.out_dir / f"{v}_{cid}.png"
        draw_chain(chain, v, out)
        print(f"已写入 {out}")
    return code


if __name__ == "__main__":
    sys.exit(main())
