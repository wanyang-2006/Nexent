"""自检脚本：逐个列出答案表中每个账户在各规则版本下的命中规则、角色、状态、是否被追到，
并核对演示账户的设计预期。结果写入 eval/selfcheck_v1.txt、selfcheck_v2.txt。

用法（仓库根目录）：
  python -m core.selfcheck                 # v1、v2，写文件并打印摘要
  python -m core.selfcheck --versions v2 --no-write

本文件在防泄题白名单内，可以读取答案目录；工具代码不得 import 本文件。
“预期”列来自 eval/demo_accounts.md 的设计推断，跑完后以本脚本输出的“实测”为准更新该文档。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import trace
from .evaluate import ANSWER_DIR, evaluate_version, load_answers
from .ruleset import norm_version
from .store import get_store

# 演示账户：账户 → (用途, v1 设计预期, v2 设计预期)，与 eval/demo_accounts.md 一致
DEMO = {
    "A0209": ("Q1 中转账户（C07 的 L2）", "建议人工复核", "建议人工复核"),
    "A0044": ("Q2 受骗付款账户（C07）", "存在风险信号", "存在风险信号"),
    "A0105": ("Q3 领工资的员工", "未见异常", "未见异常"),
    "A0176": ("Q5 v2 才变化（C05 一级收款端）", "存在风险信号", "建议人工复核"),
    "A0074": ("备用 高频商户", "证据不足", "证据不足"),
    "A0015": ("C05 受骗方", "未见异常", "存在风险信号"),
    "A0146": ("C05 受骗方", "未见异常", "存在风险信号"),
    "A0127": ("D3 的 F", "未见异常", "存在风险信号"),
    "A0104": ("D3 的 P", "未见异常", "证据不足"),
    "A0168": ("D3 的 L", "未见异常", "存在风险信号"),
}


def _rules_text(j: dict) -> str:
    return "、".join(j["H"]) or "-"


def report(st, version: str, rows: list[dict], atx: dict) -> tuple[str, dict]:
    r = evaluate_version(st, version, rows, atx)
    J = r["judgments"]
    L = [f"# selfcheck {version}  数据集 {st.dataset_id}  追链窗口 W={trace.index(st, version)['window_min']} 分钟",
         "# 列：账户 | 答案链 | 模式 | 答案角色 | 系统角色 | 主链 | 风险规则 | 反向规则 | 状态 | 角色一致",
         ""]
    role_bad = []
    for row in rows:
        a = row["acct_id"]
        j = J[a]
        ok = "是" if j["role"] == row["role"] else "否"
        if ok == "否":
            role_bad.append(a)
        L.append(" | ".join([a, row["chain_id"] or "-", row["pattern"], row["role"], j["role"], j["chain_id"] or "-",
                             _rules_text(j), "、".join(j["K"]) or "-", j["status"], ok]))

    L += ["", "## 答案链识别情况（系统链覆盖答案链 ≥60% 账户算识别）"]
    for cid, x in r["matches"].items():
        c = x["system"]
        L.append(f"{cid}: " + (f"识别为 {c['chain_id']}，hops={c['hops']}，覆盖 {x['covered']}/{len(x['accounts'])}，"
                              f"总额 {c['total_amount']}，历时 {c['duration_minutes']} 分钟" if c else "未识别"))
    L += ["", "## 未对应任何答案链的系统链"]
    L += [f"{c['chain_id']}: {'、'.join(c['accounts'])}（hops={c['hops']}）" for c in r["unmatched_system_chains"]] or ["无"]

    vi = 1 if version == "v1" else 2 if version == "v2" else None
    demo_bad = []
    L += ["", "## 演示账户（预期为设计推断）", "账户 | 用途 | 预期 | 实测 | 风险规则 | 反向规则 | 主链 | 角色 | 一致"]
    for a, info in DEMO.items():
        if a not in J:
            L.append(f"{a} | {info[0]} | - | 账户不存在 | | | | | 否")
            demo_bad.append(a)
            continue
        j = J[a]
        exp = info[vi] if vi else "-"
        same = "是" if exp == j["status"] else "否"
        if vi and same == "否":
            demo_bad.append(a)
        L.append(" | ".join([a, info[0], exp, j["status"], _rules_text(j), "、".join(j["K"]) or "-",
                             j["chain_id"] or "-", j["role"], same]))

    L += ["", "## 背景账户告警（不在答案表、状态不是未见异常）"]
    L += [f"{a} | {J[a]['status']} | {_rules_text(J[a])} | {J[a]['chain_id'] or '-'}" for a in r["background_alerts"]] or ["无"]

    summary = {
        "version": version,
        "detected": f"{r['detected']}/{r['planted']}",
        "system_chains": r["system_chains"],
        "acct_recall": f"{r['acct_recall'][0]}/{r['acct_recall'][1]}",
        "false_pos": len(r["false_pos"]),
        "role_mismatch": role_bad,
        "demo_mismatch": demo_bad,
        "background_alerts": len(r["background_alerts"]),
    }
    L += ["", "## 摘要", *(f"{k}: {v}" for k, v in summary.items())]
    return "\n".join(L) + "\n", summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="自检：写 eval/selfcheck_<版本>.txt")
    ap.add_argument("--versions", nargs="+", default=["v1", "v2"])
    ap.add_argument("--out-dir", type=Path, default=ANSWER_DIR)
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    a.versions = [norm_version(v) or v for v in a.versions]
    st = get_store()
    rows, atx = load_answers()
    for v in a.versions:
        text, s = report(st, v, rows, atx)
        if not a.no_write:
            p = a.out_dir / f"selfcheck_{v}.txt"
            with p.open("w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            print(f"已写入 {p}")
        print(f"[{v}] 识别链路 {s['detected']}，系统链 {s['system_chains']} 条，账户召回 {s['acct_recall']}，"
              f"误报 {s['false_pos']}，背景告警 {s['background_alerts']}")
        print(f"[{v}] 角色与答案不一致：{'、'.join(s['role_mismatch']) or '无'}")
        print(f"[{v}] 演示账户与设计预期不一致：{'、'.join(s['demo_mismatch']) or '无'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
