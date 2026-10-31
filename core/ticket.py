"""状态判定与证据工单（03 规范第 3 至 5 节）。

judge(st, acct, version) 给出一个账户在某规则版本下的判定要素（rejudge、selfcheck、evaluate 共用）；
ticket_result(...) 组装工单，write_ticket(...) 落盘到 tickets/<版本>/<账户>.json。

状态（按顺序命中即停）：
  1. H 为空 且 不在链上                                  → 未见异常 CLEAR
  2. |H| ≥ 2 且 在链上 且 角色 ∈ {一级收款端, 中转端, 拆分端} → 建议人工复核 REVIEW
  3. H 非空 且 K 非空                                    → 证据不足 INSUFFICIENT
  4. 其他                                                → 存在风险信号 RISK_SIGNAL
H：命中的风险规则（含 R07、R11）；K：命中的反向规则。

工单只用于辅助研判，conclusion 不得出现 enums.yaml 的禁用词；建议动作由状态唯一决定。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from . import rules, trace
from .ruleset import ROOT, fmt_amount, gap_desc, load_enums, load_ruleset, rule_by_id, rule_sort_key, status_info

TICKET_DIR_ENV = "FUNDTRACE_TICKET_DIR"          # 测试时改到临时目录，避免样例数据写进 tickets/
REVIEW_ROLES = {"一级收款端", "中转端", "拆分端"}
FIRST_CP_RULES = {"R08", "R11"}                    # 命中时附 GAP_HISTORY，并在证据描述中标“首次交易对手”
MAX_SUPPORT = 10


def ticket_dir() -> Path:
    return Path(os.environ.get(TICKET_DIR_ENV) or ROOT / "tickets")


def judge(st, acct_id: str, version: str) -> dict:
    """判定要素：hits/counter（check_rules 结果）、H、K、主链、角色、状态。"""
    cr = rules.check_rules_result(st, acct_id, version)
    H = [h["rule_id"] for h in cr["hits"]]
    K = [h["rule_id"] for h in cr["counter"]]
    chain = trace.main_chain(st, version, acct_id)
    on_chain = chain is not None
    role = chain["roles"][acct_id] if chain else "无"
    if not H and not on_chain:
        status = "未见异常"
    elif len(H) >= 2 and on_chain and role in REVIEW_ROLES:
        status = "建议人工复核"
    elif H and K:
        status = "证据不足"
    else:
        status = "存在风险信号"
    return {"acct_id": acct_id, "rule_version": version, "checks": cr, "H": H, "K": K,
            "on_chain": on_chain, "chain": chain, "chain_id": chain["chain_id"] if chain else None,
            "role": role, "status": status}


def _tx_desc(t: dict, acct_id: str, first_cp: set) -> str:
    amt = fmt_amount(t["amount"])
    if t["to_acct"] == acct_id:
        kind = "转入" if t["tx_type"] == "转账" else f"{t['tx_type']}转入"
        s = f"{t['time']} 收到 {t['from_acct']} {kind} {amt} 元"
        return s + ("（首次交易对手）" if t["tx_id"] in first_cp else "")
    if t["to_acct"] == "CASH":
        return f"{t['time']} 提现 {amt} 元（现金出口 CASH）"
    kind = "转出" if t["tx_type"] == "转账" else f"{t['tx_type']}转出"
    if t["from_acct"] != acct_id:
        return f"{t['time']} {t['from_acct']} 向 {t['to_acct']} {kind} {amt} 元（链上其他账户交易）"
    return f"{t['time']} 向 {t['to_acct']} {kind} {amt} 元"


def _conclusion(j: dict) -> str:
    st, cid, role = j["status"], j["chain_id"], j["role"]
    h = "、".join(j["H"])
    k = "、".join(j["K"])
    on = f"该账户在资金链 {cid} 中表现为{role}，" if cid else "该账户"
    if st == "建议人工复核":
        return f"{on}命中 {len(j['H'])} 条风险规则（{h}），建议人工复核。"
    if st == "证据不足":
        return f"{on}命中风险规则（{h}），同时存在反向证据（{k}），现有证据不足以判断，建议补充材料。"
    if st == "存在风险信号":
        hit = f"命中 {h}，" if h else ""
        return f"{on}{hit}存在风险信号，建议关注后续交易。"
    return "在本数据范围内未发现风险规则命中，也不在已识别的资金链上。"


def ticket_result(st, acct_id: str, version: str) -> dict:
    """组装工单（字段顺序同 schemas/make_ticket.schema.json）。参数已由 api 层校验。"""
    rs = load_ruleset(version)
    j = judge(st, acct_id, version)
    cr, chain = j["checks"], j["chain"]
    tx_by = st.tx_by_id

    # 首次对手的交易：R08 / R11 的证据
    first_cp = {x for h in cr["hits"] if h["rule_id"] in FIRST_CP_RULES for x in h["evidence_tx_ids"]}

    # 支持证据：本账户在主链上的边优先，再用风险规则证据补足；去重、最多 10 条、按时间升序
    by_time = lambda xs: sorted((tx_by[x] for x in xs), key=lambda t: (t["time"], t["tx_id"]))
    chain_ids = {e["tx_id"] for e in chain["edges"] if acct_id in (e["from_acct"], e["to_acct"])} if chain else set()
    rule_ids = {x for h in cr["hits"] for x in h["evidence_tx_ids"]} - chain_ids
    picked = by_time(chain_ids)[:MAX_SUPPORT]
    picked += by_time(rule_ids)[:MAX_SUPPORT - len(picked)]
    support_txs = sorted(picked, key=lambda t: (t["time"], t["tx_id"]))
    supporting = [{"tx_id": t["tx_id"], "desc": _tx_desc(t, acct_id, first_cp)} for t in support_txs]

    counter = [{"rule_id": h["rule_id"], "rule_name": h["rule_name"], "desc": h["detail"],
                "tx_ids": list(h["evidence_tx_ids"])} for h in cr["counter"]]

    gaps = ["GAP_KYC"]
    if supporting:
        gaps.append("GAP_MEMO_DEVICE")
    if j["on_chain"]:
        gaps.append("GAP_CALLBACK")
        if any(t["to_acct"] == "CASH" for a in chain["accounts"] for t in st.account_txs(a)):
            gaps.append("GAP_EXT")
    if FIRST_CP_RULES & set(j["H"]):
        gaps.append("GAP_HISTORY")
    if j["K"]:
        gaps.append("GAP_BIZ")
    missing = [{"code": g, "desc": gap_desc(g)} for g in gaps]

    basis = []
    for rid in sorted(j["H"] + j["K"], key=rule_sort_key):
        r = rule_by_id(rs, rid)
        basis.append({"rule_id": rid, "rule_name": r["name"], "aligned_to": r["aligned_to"]})

    info = status_info()[j["status"]]
    return {
        "ticket_id": f"TK-{version}-{acct_id}",
        "spec_version": rs.get("spec_version") or load_enums().get("spec_version"),
        "acct_id": acct_id,
        "rule_version": version,
        "status": j["status"],
        "status_code": info["code"],
        "role": j["role"],
        "chain_id": j["chain_id"],
        "conclusion": _conclusion(j),
        "supporting_evidence": supporting,
        "counter_evidence": counter,
        "missing_evidence": missing,
        "rule_basis": basis,
        "suggested_actions": [info["action"]] if info["action"] else [],
    }


def write_ticket(ticket: dict) -> Path:
    """落盘：tickets/<版本>/<账户>.json，UTF-8、LF、indent=2。"""
    d = ticket_dir() / ticket["rule_version"]
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{ticket['acct_id']}.json"
    with p.open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(ticket, ensure_ascii=False, indent=2) + "\n")
    return p
