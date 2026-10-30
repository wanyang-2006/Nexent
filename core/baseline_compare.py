"""对照基线（只给出基线的判定与链，不读答案目录；打分在 core/evaluate.py 中）。

B1 单笔规则：账户只要收到或付出一笔 ≥ 10000 元的转账，就判“建议人工复核”。
B2 无时序追链：候选边与本作品相同（转账、双方都是账户、金额 ≥ seed_min_amount），
   只要 e1.to == e2.from 就链接，不看时间窗和节点守恒，取弱连通分量，
   至少含 1 个链接且最大单笔 ≥ min_chain_amount。

返回的链结构与 core.trace 一致的子集：chain_id、accounts、tx_ids、edges，便于复用评测函数。
"""
from __future__ import annotations

from collections import defaultdict

from .ruleset import load_ruleset

B1_MIN_AMOUNT = 10000
B1_TX_TYPE = "转账"


def b1_flagged(st) -> set[str]:
    """B1：返回被判“建议人工复核”的账户集合。"""
    out = set()
    for t in st.transactions:
        if t["tx_type"] == B1_TX_TYPE and t["amount"] >= B1_MIN_AMOUNT:
            for a in (t["from_acct"], t["to_acct"]):
                if a in st.accounts:
                    out.add(a)
    return out


def b2_chains(st, version: str = "v1") -> list[dict]:
    """B2：只看“前一笔的收款方 == 后一笔的付款方”，不看时间与守恒。"""
    tr = load_ruleset(version)["trace"]
    accts = st.accounts
    E = [t for t in st.transactions
         if t["tx_type"] in tr["edge_types"] and t["from_acct"] in accts and t["to_acct"] in accts
         and t["amount"] >= tr["seed_min_amount"]]
    by_id = {e["tx_id"]: e for e in E}
    out_by = defaultdict(list)
    for e in E:
        out_by[e["from_acct"]].append(e)

    parent: dict[str, str] = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for e1 in E:
        for e2 in out_by[e1["to_acct"]]:
            if e2["tx_id"] != e1["tx_id"]:
                parent[find(e1["tx_id"])] = find(e2["tx_id"])
    comps = defaultdict(list)
    for x in list(parent):
        comps[find(x)].append(x)

    chains = []
    for members in comps.values():
        es = sorted((by_id[x] for x in members), key=lambda e: (e["time"], e["tx_id"]))
        if max(e["amount"] for e in es) < tr["min_chain_amount"]:
            continue
        accs = sorted({e["from_acct"] for e in es} | {e["to_acct"] for e in es})
        chains.append({
            "chain_id": "B2-" + min(e["tx_id"] for e in es),
            "accounts": accs,
            "tx_ids": sorted(e["tx_id"] for e in es),
            "edges": [{"tx_id": e["tx_id"], "from_acct": e["from_acct"], "to_acct": e["to_acct"],
                       "time": e["time"], "amount": e["amount"]} for e in es],
        })
    chains.sort(key=lambda c: c["chain_id"])
    return chains
