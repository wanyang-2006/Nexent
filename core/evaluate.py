"""评测脚本（03 规范第 7 节）：按规则版本统计识别链路数、账户召回、误报等，写入 eval/result.md。

用法（仓库根目录）：
  python -m core.evaluate                       # v1、v2 两列，写 eval/result.md
  python -m core.evaluate --no-write            # 只打印

本文件在防泄题白名单内，可以读取答案目录；工具代码（api/trace/rules/ticket/rejudge）不得 import 本文件。
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

from . import trace
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


def match_chains(st, version: str, rows: list[dict]) -> dict:
    """答案链 → 覆盖其 ≥60% 账户的系统链（取覆盖最多者；没有为 None）。"""
    groups = {}
    for r in rows:
        if r["chain_id"]:
            groups.setdefault(r["chain_id"], set()).add(r["acct_id"])
    sys_chains = trace.all_chains(st, version)
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
