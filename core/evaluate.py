"""评测脚本（03 规范第 7 节）：按规则版本统计识别链路数、账户召回、误报等，写入 eval/result.md。

用法（仓库根目录）：
  python -m core.evaluate                       # v1、v2 两列，写 eval/result.md
  python -m core.evaluate --no-write            # 只打印
  同时写 eval/baseline.md（对照基线，见 core/baseline_compare.py）

本文件在防泄题白名单内，可以读取答案目录；工具代码（api/trace/rules/ticket/rejudge）不得 import 本文件。
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

from . import baseline_compare, trace
from .rejudge import rejudge_result
from .ruleset import ROOT, norm_version
from .store import get_store
from .ticket import judge

ANSWER_DIR = ROOT / "eval"
TARGET_ROLES = {"一级收款端", "中转端", "拆分端"}
COVER = 0.6


def load_answers(answer_dir: Path = ANSWER_DIR):
    """返回 (answer 行列表, answer_tx 的 {tx_id: chain_id})。"""
    with (answer_dir / "answer.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    atx = {}
    p = answer_dir / "answer_tx.csv"
    if p.exists():
        with p.open(encoding="utf-8", newline="") as f:
            atx = {r["tx_id"]: r["chain_id"] for r in csv.DictReader(f)}
    return rows, atx


def judge_all(st, version: str) -> dict:
    return {a: judge(st, a, version) for a in sorted(st.accounts)}


def match_chains(st, version: str, rows: list[dict], sys_chains: list[dict] | None = None) -> dict:
    """答案链 → 覆盖其 ≥60% 账户的系统链（取覆盖最多者；没有为 None）。sys_chains 默认取 trace 的结果。"""
    groups = {}
    for r in rows:
        if r["chain_id"]:
            groups.setdefault(r["chain_id"], set()).add(r["acct_id"])
    sys_chains = trace.all_chains(st, version) if sys_chains is None else sys_chains
    out = {}
    for cid in sorted(groups):
        G = groups[cid]
        best = None
        for c in sys_chains:
            k = len(G & set(c["accounts"]))
            if k >= COVER * len(G) and (best is None or k > best[1]):
                best = (c, k)
        out[cid] = {"accounts": G, "system": best[0] if best else None, "covered": best[1] if best else 0}
    return out


def evaluate_version(st, version: str, rows: list[dict], atx: dict) -> dict:
    J = judge_all(st, version)
    m = match_chains(st, version, rows)
    sys_chains = trace.all_chains(st, version)
    matched_ids = {x["system"]["chain_id"] for x in m.values() if x["system"]}

    ans_edges = set(atx)
    sys_edges = {t for c in sys_chains for t in c["tx_ids"]}
    inter = ans_edges & sys_edges

    in_answer = {r["acct_id"] for r in rows}
    target = sorted({r["acct_id"] for r in rows if r["role"] in TARGET_ROLES})
    benign = sorted({r["acct_id"] for r in rows if r["role"] == "无"})
    return {
        "version": version,
        "judgments": J,
        "matches": m,
        "planted": len(m),
        "detected": sum(1 for x in m.values() if x["system"]),
        "missed": sorted(cid for cid, x in m.items() if not x["system"]),
        "system_chains": len(sys_chains),
        "unmatched_system_chains": [c for c in sys_chains if c["chain_id"] not in matched_ids],
        "edge_recall": (len(inter), len(ans_edges)),
        "edge_precision": (len(inter), len(sys_edges)),
        "acct_recall": (sum(1 for a in target if J[a]["status"] == "建议人工复核"), len(target)),
        "acct_recall_missed": [a for a in target if J[a]["status"] != "建议人工复核"],
        "false_pos": [a for a in benign if J[a]["status"] == "建议人工复核"],
        "benign_total": len(benign),
        "benign_insufficient": [a for a in benign if J[a]["status"] == "证据不足"],
        "background_alerts": [a for a in sorted(st.accounts) if a not in in_answer and J[a]["status"] != "未见异常"],
        "status_count": Counter(j["status"] for j in J.values()),
    }


def score_chains(st, version: str, rows: list[dict], atx: dict, chains: list[dict]) -> dict:
    """对任意一组链（本作品或基线）按同一口径打分。"""
    m = match_chains(st, version, rows, chains)
    in_answer = {r["acct_id"] for r in rows}
    ans_edges = set(atx)
    sys_edges = {t for c in chains for t in c["tx_ids"]}
    inter = ans_edges & sys_edges
    accts = {a for c in chains for a in c["accounts"]}
    return {
        "detected": sum(1 for x in m.values() if x["system"]),
        "planted": len(m),
        "chains": len(chains),
        "edge_recall": (len(inter), len(ans_edges)),
        "edge_precision": (len(inter), len(sys_edges)),
        "outside_accts": len(accts - in_answer),
        "chain_accts": len(accts),
        "largest": max((len(c["accounts"]) for c in chains), default=0),
    }


def score_b1(st, rows: list[dict]) -> dict:
    flagged = baseline_compare.b1_flagged(st)
    in_answer = {r["acct_id"] for r in rows}
    target = sorted({r["acct_id"] for r in rows if r["role"] in TARGET_ROLES})
    benign = sorted({r["acct_id"] for r in rows if r["role"] == "无"})
    return {
        "acct_recall": (sum(1 for a in target if a in flagged), len(target)),
        "false_pos": (sum(1 for a in benign if a in flagged), len(benign)),
        "background": len([a for a in flagged if a not in in_answer]),
        "flagged": len(flagged),
    }


def render_baseline(st, results: list[dict], rows: list[dict], atx: dict) -> str:
    own = {r["version"]: r for r in results}
    b1 = score_b1(st, rows)
    b2 = score_chains(st, "v1", rows, atx, baseline_compare.b2_chains(st, "v1"))
    own_sc = {v: score_chains(st, v, rows, atx, trace.all_chains(st, v)) for v in own}
    vs = list(own)
    cols = ["B1 单笔规则", "B2 无时序追链"] + [f"本作品 {v}" for v in vs]
    L = [
        "# 对照基线结果",
        "",
        f"- 数据集：`{st.dataset_id}`（`data/dataset_meta.json`）",
        "- 生成方式：`python -m core.evaluate`（由脚本生成，请勿手改；文档中的数字以本文件为准）",
        "- 基线定义见 `core/baseline_compare.py`：B1 = 账户只要收到或付出一笔 ≥ 10000 元的转账即判“建议人工复核”；"
        "B2 = 候选边与本作品相同，只要前一笔收款方等于后一笔付款方就链接，不看时间窗与节点守恒。",
        "- 以上均为**在本作品设定的仿真场景内**的结果；v2 演示链为专门设计，不代表真实环境的泛化效果。",
        "- B2 的链按 v1 的候选边参数生成。结论只描述上表数字，不外推到真实环境。",
        "",
        "## 账户判定（B1 与本作品）",
        "",
        "| 指标 | " + " | ".join([cols[0]] + cols[2:]) + " |",
        "|---|" + "---|" * (len(cols) - 1),
        "| 账户召回（18 个目标账户判为建议人工复核） | " + " | ".join(
            [_ratio(b1["acct_recall"])] + [_ratio(own[v]["acct_recall"]) for v in vs]) + " |",
        "| 误报账户（干扰账户判为建议人工复核） | " + " | ".join(
            [f"{b1['false_pos'][0]}/{b1['false_pos'][1]}"] + [f"{len(own[v]['false_pos'])}/{own[v]['benign_total']}" for v in vs]) + " |",
        "| 背景账户告警（不在答案表） | " + " | ".join(
            [str(b1["background"])] + [str(len(own[v]["background_alerts"])) for v in vs]) + " |",
        "| 被判建议人工复核的账户总数 | " + " | ".join(
            [str(b1["flagged"])] + [str(own[v]["status_count"].get("建议人工复核", 0)) for v in vs]) + " |",
        "",
        "## 追链（B2 与本作品）",
        "",
        "| 指标 | " + " | ".join(cols[1:]) + " |",
        "|---|" + "---|" * (len(cols) - 1),
    ]
    scs = [b2] + [own_sc[v] for v in vs]
    L.append("| 识别链路数（覆盖答案链 ≥60% 账户） | " + " | ".join(f"{x['detected']}/{x['planted']}" for x in scs) + " |")
    L.append("| 系统识别的链总数 | " + " | ".join(str(x["chains"]) for x in scs) + " |")
    L.append("| 链边召回 | " + " | ".join(_ratio(x["edge_recall"]) for x in scs) + " |")
    L.append("| 链边精确 | " + " | ".join(_ratio(x["edge_precision"]) for x in scs) + " |")
    L.append("| 链内账户总数 | " + " | ".join(str(x["chain_accts"]) for x in scs) + " |")
    L.append("| 混入链中的非答案账户数 | " + " | ".join(str(x["outside_accts"]) for x in scs) + " |")
    L.append("| 最大一条链的账户数 | " + " | ".join(str(x["largest"]) for x in scs) + " |")
    v1, v2 = own.get("v1"), own.get("v2")
    L += ["", "## 解读（由数字生成）", ""]
    if v1:
        L.append(f"- 账户判定：B1 把 {b1['flagged']} 个账户判为建议人工复核，本作品 v1 为 "
                 f"{v1['status_count'].get('建议人工复核', 0)} 个；B1 召回 {_ratio(b1['acct_recall'])}，"
                 f"误报 {b1['false_pos'][0]}/{b1['false_pos'][1]}，本作品 v1 召回 {_ratio(v1['acct_recall'])}，"
                 f"误报 {len(v1['false_pos'])}/{v1['benign_total']}。B1 召回不低，代价是待人工复核的账户更多、且有干扰账户被误判。")
    same = [v for v in vs if own_sc[v]["detected"] == b2["detected"] and own_sc[v]["edge_recall"] == b2["edge_recall"]
            and own_sc[v]["edge_precision"] == b2["edge_precision"] and own_sc[v]["chains"] == b2["chains"]]
    if same:
        L.append(f"- 追链：B2（不看时间窗与守恒）在本数据集上与本作品 {'、'.join(same)} 的链指标相同。"
                 "可能的原因（推断，未单独验证）：数据中没有“账户相同但时间不相邻”的干扰转账，"
                 "不看时序也不会把不相关的交易接到一起。因此不能据此说明时序追链在真实数据上更优，"
                 "该对比只说明本数据集中两种追链结果一致。")
    L.append("- 本作品 v1 与 v2 的差别来自 R01 时间窗由 60 分钟放宽到 120 分钟，是规则参数变化引起的结论变化，不是基线对比。")
    return "\n".join(L) + "\n"


def _ratio(pair) -> str:
    k, n = pair
    return f"{k}/{n}（{k / n * 100:.1f}%）" if n else "0/0"


def render(st, results: list[dict], rj: dict | None) -> str:
    vs = [r["version"] for r in results]
    head = "| 指标 | " + " | ".join(vs) + " |"
    sep = "|---|" + "---|" * len(vs)

    def row(name, fn):
        return f"| {name} | " + " | ".join(fn(r) for r in results) + " |"

    L = [
        "# 评测结果",
        "",
        f"- 数据集：`{st.dataset_id}`（`data/dataset_meta.json`）",
        f"- 规则版本：{'、'.join(vs)}",
        "- 生成方式：`python -m core.evaluate`（由脚本生成，请勿手改；文档中的数字以本文件为准）",
        "- 口径：`Data and Rules/03_判定与输出规范.md` 第 7 节。以下结果均为**在本作品设定的仿真场景内**的结果；"
        "v2 演示链为专门设计，用于说明规则变化引起结论变化，不代表真实环境的泛化效果。",
        "",
        "## 主要指标",
        "",
        head, sep,
        row("埋入链路数", lambda r: str(r["planted"])),
        row("识别链路数（系统链覆盖答案链 ≥60% 账户）", lambda r: str(r["detected"])),
        row("漏检链路数", lambda r: str(r["planted"] - r["detected"])),
        row("系统识别的链总数", lambda r: str(r["system_chains"])),
        row("链边召回", lambda r: _ratio(r["edge_recall"])),
        row("链边精确", lambda r: _ratio(r["edge_precision"])),
        row("账户召回（一级收款端/中转端/拆分端判为建议人工复核）", lambda r: _ratio(r["acct_recall"])),
        row("误报账户数（干扰账户判为建议人工复核）", lambda r: f"{len(r['false_pos'])}/{r['benign_total']}"),
        row("证据不足（干扰账户）", lambda r: str(len(r["benign_insufficient"]))),
        row("背景账户告警（不在答案表、状态不是未见异常）", lambda r: str(len(r["background_alerts"]))),
        "",
        "## 全部账户的状态分布",
        "",
        head, sep,
    ]
    for s in ("未见异常", "存在风险信号", "证据不足", "建议人工复核"):
        L.append(row(s, lambda r, s=s: str(r["status_count"].get(s, 0))))

    for r in results:
        v = r["version"]
        L += ["", f"## 明细（{v}）", ""]
        L.append(f"- 漏检的答案链：{'、'.join(r['missed']) or '无'}")
        extra = [f"{c['chain_id']}（{'、'.join(c['accounts'])}）" for c in r["unmatched_system_chains"]]
        L.append(f"- 未对应任何答案链的系统链：{'；'.join(extra) or '无'}")
        miss = [f"{a}（{r['judgments'][a]['status']}）" for a in r["acct_recall_missed"]]
        L.append(f"- 账户召回未命中：{'、'.join(miss) or '无'}")
        L.append(f"- 误报账户：{'、'.join(r['false_pos']) or '无'}")
        L.append(f"- 证据不足的干扰账户：{'、'.join(r['benign_insufficient']) or '无'}")
        bg = [f"{a}（{r['judgments'][a]['status']}，{'、'.join(r['judgments'][a]['H']) or '仅在链上'}）" for a in r["background_alerts"]]
        L.append(f"- 背景账户告警：{'、'.join(bg) or '无'}")
        L += ["", "| 答案链 | 账户数 | 对应系统链 | 覆盖账户数 | hops |", "|---|---|---|---|---|"]
        for cid, x in r["matches"].items():
            c = x["system"]
            L.append(f"| {cid} | {len(x['accounts'])} | {c['chain_id'] if c else '—'} | {x['covered']} | {c['hops'] if c else '—'} |")

    if rj:
        s = rj["summary"]
        L += ["", f"## 状态变化（rejudge {rj['old']}→{rj['new']}）", "",
              f"全部 {s['total']} 个账户中 {s['changed']} 个状态变化：升级 {s['upgraded']}，降级 {s['downgraded']}。", "",
              "| 变化 | 账户数 |", "|---|---|"]
        L += [f"| {k} | {n} |" for k, n in s["by_transition"].items()]
        L += ["", "| 账户 | 旧状态 | 新状态 | 原因 |", "|---|---|---|---|"]
        L += [f"| {c['acct_id']} | {c['old_status']} | {c['new_status']} | {c['reason']} |" for c in rj["changed"]]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="评测：写 eval/result.md")
    ap.add_argument("--versions", nargs="+", default=["v1", "v2"])
    ap.add_argument("--out", type=Path, default=ANSWER_DIR / "result.md")
    ap.add_argument("--baseline-out", type=Path, default=ANSWER_DIR / "baseline.md")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    a.versions = [norm_version(v) or v for v in a.versions]
    st = get_store()
    rows, atx = load_answers()
    results = [evaluate_version(st, v, rows, atx) for v in a.versions]
    rj = rejudge_result(st, a.versions[0], a.versions[1]) if len(a.versions) >= 2 else None
    text = render(st, results, rj)
    print(text)
    if not a.no_write:
        with a.out.open("w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"已写入 {a.out}")
        btext = render_baseline(st, results, rows, atx)
        with a.baseline_out.open("w", encoding="utf-8", newline="\n") as f:
            f.write(btext)
        print(f"已写入 {a.baseline_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
