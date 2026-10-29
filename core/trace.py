"""资金链追踪（02 规范第 5 节）。由 validate_spec.py 的 reference_chains 移植，结果须与之逐项一致。

定义（链接图）：
1. 候选边：tx_type ∈ trace.edge_types，双方都是账户（不含 CASH），金额 ≥ seed_min_amount。
2. 链接 e1→e2：e1.to == e2.from == v；e1.t < e2.t ≤ e1.t + W；
   v 在 (e1.t, e1.t+W] 的候选转出合计 ≥ conserve_ratio × e1.amount（向下守恒）；
   v 在 [e2.t−W, e2.t) 的候选转入合计 ≥ conserve_ratio × e2.amount（向上守恒）。
3. 资金链：链接图的弱连通分量，至少含 1 个链接，且最大单笔 ≥ min_chain_amount。
4. 每个规则版本对全部数据算一次并缓存（W 取自 R01.window_min，所以 v2 改 R01 会改变追链结果）。

只读 data/（经 store），不读答案目录。
"""
from __future__ import annotations

from collections import defaultdict

from .ruleset import load_ruleset, resolve_window, rule_by_id, to_min

DEFAULT_MIN_RECEIVERS = 4      # 规则集里没有 R03 时的拆分端阈值（与参考实现一致）


def _build(st, version: str) -> dict:
    rs = load_ruleset(version)
    tr = rs["trace"]
    W, cr = resolve_window(rs), tr["conserve_ratio"]
    max_edges = tr.get("max_component_edges", 500)
    accts = st.accounts

    E = []
    for t in st.transactions:
        if (t["tx_type"] in tr["edge_types"] and t["from_acct"] in accts and t["to_acct"] in accts
                and t["amount"] >= tr["seed_min_amount"]):
            E.append({"tx_id": t["tx_id"], "from_acct": t["from_acct"], "to_acct": t["to_acct"],
                      "time": t["time"], "amount": t["amount"], "t": to_min(t["time"])})
    by_id = {e["tx_id"]: e for e in E}
    out_by, in_by = defaultdict(list), defaultdict(list)
    for e in E:
        out_by[e["from_acct"]].append(e)
        in_by[e["to_acct"]].append(e)

    def out_sum(v, lo, hi):          # (lo, hi]
        return sum(x["amount"] for x in out_by[v] if lo < x["t"] <= hi)

    def in_sum(v, lo, hi):           # [lo, hi)
        return sum(x["amount"] for x in in_by[v] if lo <= x["t"] < hi)

    succ, pred = defaultdict(set), defaultdict(set)
    for e1 in E:
        v = e1["to_acct"]
        if out_sum(v, e1["t"], e1["t"] + W) < cr * e1["amount"]:
            continue
        for e2 in out_by[v]:
            if e1["t"] < e2["t"] <= e1["t"] + W and in_sum(v, e2["t"] - W, e2["t"]) >= cr * e2["amount"]:
                succ[e1["tx_id"]].add(e2["tx_id"])
                pred[e2["tx_id"]].add(e1["tx_id"])

    parent: dict[str, str] = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, bs in succ.items():
        for b in bs:
            parent[find(a)] = find(b)
    comps = defaultdict(list)
    for x in list(parent):
        comps[find(x)].append(x)

    r03 = rule_by_id(rs, "R03")
    min_recv = r03["params"]["min_receivers"] if r03 else DEFAULT_MIN_RECEIVERS
    chains = []
    for members in comps.values():
        es = sorted((by_id[x] for x in members), key=lambda e: (e["t"], e["tx_id"]))
        if max(e["amount"] for e in es) < tr["min_chain_amount"]:
            continue
        # 最长路径（边数）：链接严格按时间递增，倒序遍历即可保证后继先算完
        longest = {}
        for e in reversed(es):
            longest[e["tx_id"]] = 1 + max((longest[y] for y in succ[e["tx_id"]]), default=0)
        sources = [e for e in es if not pred[e["tx_id"]]]

        indeg, outdeg = defaultdict(int), defaultdict(int)
        recv, preds = defaultdict(set), defaultdict(set)
        for e in es:
            outdeg[e["from_acct"]] += 1
            indeg[e["to_acct"]] += 1
            recv[e["from_acct"]].add(e["to_acct"])
            preds[e["to_acct"]].add(e["from_acct"])
        accs = {e["from_acct"] for e in es} | {e["to_acct"] for e in es}

        # 角色（03 规范第 3 节，按顺序命中即停）
        roles = {a: "疑似受骗付款端" for a in accs if indeg[a] == 0}
        for a in accs:
            if a in roles:
                continue
            if outdeg[a] == 0:
                roles[a] = "末端"
            elif len(recv[a]) >= min_recv:
                roles[a] = "拆分端"
            elif all(roles.get(p) == "疑似受骗付款端" for p in preds[a]):
                roles[a] = "一级收款端"
            else:
                roles[a] = "中转端"

        # 账户排序：距源点深度（账户图 BFS），再按账户号
        depth = {a: 0 for a in accs if indeg[a] == 0}
        frontier = sorted(depth)
        while frontier:
            nxt = []
            for a in frontier:
                for b in sorted(recv[a]):
                    if b not in depth:
                        depth[b] = depth[a] + 1
                        nxt.append(b)
            frontier = nxt
        ordered = sorted(accs, key=lambda a: (depth.get(a, 99), a))

        chains.append({
            "chain_id": "L-" + min(e["tx_id"] for e in es),
            "hops": max(longest.values()),
            "total_amount": sum(e["amount"] for e in sources),
            "duration_minutes": es[-1]["t"] - es[0]["t"],
            "accounts": ordered,
            "tx_ids": sorted(e["tx_id"] for e in es),
            "edges": [{"tx_id": e["tx_id"], "from_acct": e["from_acct"], "to_acct": e["to_acct"],
                       "time": e["time"], "amount": e["amount"]} for e in es],
            "roles": {a: roles[a] for a in ordered},
            "_too_big": len(es) > max_edges,
            "_max_edges": max_edges,
        })
    chains.sort(key=lambda c: (-c["total_amount"], c["chain_id"]))

    by_acct = defaultdict(list)
    for c in chains:                       # 已按 (total_amount 降序, chain_id 升序)，每个账户的列表保持这个顺序
        for a in c["accounts"]:
            by_acct[a].append(c)
    return {"version": version, "window_min": W, "chains": chains, "by_acct": dict(by_acct)}


def index(st, version: str) -> dict:
    """某规则版本的全量追链结果（缓存）。"""
    return st.cached(("trace", version), lambda: _build(st, version))


def all_chains(st, version: str) -> list[dict]:
    return index(st, version)["chains"]


def chains_of(st, version: str, acct_id: str) -> list[dict]:
    """包含该账户的全部链，按 total_amount 降序、chain_id 升序。"""
    return index(st, version)["by_acct"].get(acct_id, [])


def main_chain(st, version: str, acct_id: str) -> dict | None:
    """主链：total_amount 最大，相同时 chain_id 较小（即 chains_of 的第一条）。"""
    cs = chains_of(st, version, acct_id)
    return cs[0] if cs else None


def role_in_main_chain(st, version: str, acct_id: str) -> str:
    c = main_chain(st, version, acct_id)
    return c["roles"][acct_id] if c else "无"


def view(chain: dict, acct_id: str, max_hops: int) -> dict:
    """对外返回的链（02 规范 5.3）。max_hops 只裁剪 edges：在链的无向账户图中从查询账户 BFS，
    保留两端距离都 ≤ max_hops 的边；若因此不足 2 条（schema 要求），放宽为“至少一端 ≤ max_hops”。
    chain_id、hops、total_amount、duration_minutes、accounts、tx_ids、roles 始终描述整条链。"""
    edges = chain["edges"]
    adj = defaultdict(set)
    for e in edges:
        adj[e["from_acct"]].add(e["to_acct"])
        adj[e["to_acct"]].add(e["from_acct"])
    dist, frontier = {acct_id: 0}, [acct_id]
    while frontier:
        nxt = []
        for a in frontier:
            for b in sorted(adj[a]):
                if b not in dist:
                    dist[b] = dist[a] + 1
                    nxt.append(b)
        frontier = nxt
    far = 10 ** 9
    kept = [e for e in edges if max(dist.get(e["from_acct"], far), dist.get(e["to_acct"], far)) <= max_hops]
    if len(kept) < 2:
        kept = [e for e in edges if min(dist.get(e["from_acct"], far), dist.get(e["to_acct"], far)) <= max_hops]
    if chain["_too_big"]:
        kept = kept[:chain["_max_edges"]]
    return {
        "chain_id": chain["chain_id"],
        "hops": chain["hops"],
        "total_amount": chain["total_amount"],
        "duration_minutes": chain["duration_minutes"],
        "accounts": list(chain["accounts"]),
        "tx_ids": list(chain["tx_ids"]),
        "edges": [dict(e) for e in kept],
        "roles": dict(chain["roles"]),
        "truncated": chain["_too_big"] or len(kept) < len(edges),
    }


def trace_chain_result(st, acct_id: str, max_hops: int, version: str) -> dict:
    """trace_chain 的返回对象（参数已由 api 层校验）。"""
    idx = index(st, version)
    return {
        "acct_id": acct_id,
        "rule_version": version,
        "window_min": idx["window_min"],
        "max_hops": max_hops,
        "chains": [view(c, acct_id, max_hops) for c in idx["by_acct"].get(acct_id, [])],
    }
