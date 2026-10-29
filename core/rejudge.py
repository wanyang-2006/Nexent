"""规则版本重判（03 规范第 6 节）：对 accounts.csv 全部账户分别按两个版本判定，只列状态变化的账户。

reason 由以下片段按顺序用“；”连接：
  1. 每条新增命中：新命中 R01（快进快出，window_min 60→120）；参数无变化时省略参数部分；新规则写“v2 新增规则”
  2. 每条不再命中：不再命中 R0x（名称）
  3. 链变化：进入资金链 L-…（角色）/ 离开资金链 L-… / 所在资金链由 L-… 变为 L-…
"""
from __future__ import annotations

from .ruleset import load_ruleset, rule_by_id, rule_sort_key, rules_diff, status_info
from .ticket import judge


def _rule_changes(old_v: str, new_v: str) -> dict:
    """规则号 → “window_min 60→120” 形式的变化说明（参数、口径、等级、状态；与 rules_diff 一致）。"""
    out = {}
    for c in rules_diff(load_ruleset(old_v), load_ruleset(new_v))["changed"]:
        field = c["field"].removeprefix("params.")
        out.setdefault(c["rule_id"], []).append(f"{field} {c['old']}→{c['new']}")
    return {rid: "，".join(parts) for rid, parts in out.items()}


def _reason(old_v: str, new_v: str, jo: dict, jn: dict, added: list[str], removed: list[str]) -> str:
    rs_o, rs_n = load_ruleset(old_v), load_ruleset(new_v)
    changes = _rule_changes(old_v, new_v)
    parts = []
    for rid in added:
        rn, ro = rule_by_id(rs_n, rid), rule_by_id(rs_o, rid)
        if ro is None:
            parts.append(f"新命中 {rid}（{rn['name']}，{new_v} 新增规则）")
        else:
            ch = changes.get(rid)
            parts.append(f"新命中 {rid}（{rn['name']}，{ch}）" if ch else f"新命中 {rid}（{rn['name']}）")
    for rid in removed:
        r = rule_by_id(rs_o, rid) or rule_by_id(rs_n, rid)
        parts.append(f"不再命中 {rid}（{r['name']}）")
    oc, nc = jo["chain_id"], jn["chain_id"]
    if oc is None and nc is not None:
        parts.append(f"进入资金链 {nc}（{jn['role']}）")
    elif oc is not None and nc is None:
        parts.append(f"离开资金链 {oc}")
    elif oc != nc:
        parts.append(f"所在资金链由 {oc} 变为 {nc}")
    elif oc is not None and jo["role"] != jn["role"]:
        parts.append(f"在资金链 {nc} 中的角色由{jo['role']}变为{jn['role']}")
    return "；".join(parts) or "命中规则与所在资金链均未变化（判定条件组合变化）"


def rejudge_result(st, old_v: str, new_v: str) -> dict:
    """rejudge 的返回对象。参数已由 api 层校验。"""
    sev = {k: v["severity"] for k, v in status_info().items()}
    changed, by_tr = [], {}
    for a in sorted(st.accounts):
        jo, jn = judge(st, a, old_v), judge(st, a, new_v)
        if jo["status"] == jn["status"]:
            continue
        ro, rn = set(jo["H"] + jo["K"]), set(jn["H"] + jn["K"])
        added = sorted(rn - ro, key=rule_sort_key)
        removed = sorted(ro - rn, key=rule_sort_key)
        changed.append({
            "acct_id": a,
            "old_status": jo["status"],
            "new_status": jn["status"],
            "direction": "升级" if sev[jn["status"]] > sev[jo["status"]] else "降级",
            "old_role": jo["role"],
            "new_role": jn["role"],
            "old_chain_id": jo["chain_id"],
            "new_chain_id": jn["chain_id"],
            "rule_changes": {"added": added, "removed": removed},
            "reason": _reason(old_v, new_v, jo, jn, added, removed),
        })
        key = f"{jo['status']}→{jn['status']}"
        by_tr[key] = by_tr.get(key, 0) + 1
    up = sum(1 for c in changed if c["direction"] == "升级")
    return {
        "old": old_v,
        "new": new_v,
        "changed": changed,
        "summary": {"total": len(st.accounts), "changed": len(changed), "upgraded": up,
                    "downgraded": len(changed) - up, "by_transition": dict(sorted(by_tr.items()))},
    }
