"""规则引擎（02 规范第 2 至 4 节）。按 YAML 中每条规则的 impl 分发到 IMPLS 中的函数。

- 新增规则：在 enums.yaml 登记 impl（复用已有 impl 可跳过）→ 新建 rules_vN.yaml → 若是新 impl，在此实现并加入 IMPLS。
- YAML 中出现未实现的 impl 时直接报错（返回 INTERNAL），防止漏实现。
- 每条命中：{rule_id, rule_name, type, level, evidence_tx_ids, detail, metrics?}；
  证据按时间升序、去重、最多 evidence_limit 条；多个窗口都命中时取规则表写明的“代表窗口”，并列时取最早的。
- 时间窗：聚合窗口 [t, t+W]（从锚点交易起，同一分钟内按 tx_id 先后），前向窗口 (t, t+W]（按分钟）。

只读 data/（经 store），不读答案目录。
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date

from . import trace
from .ruleset import active_rules, fmt_amount, load_ruleset, to_min
from .store import CASH


# ------------------------------------------------------------------ 账户上下文
class Ctx:
    """一个账户在一个规则版本下的计算上下文。"""

    def __init__(self, st, version: str, acct_id: str):
        self.st, self.version, self.acct = st, version, acct_id
        self.row = st.accounts[acct_id]
        self.txs = st.account_txs(acct_id)          # 按 (time, tx_id) 升序
        self.rs = load_ruleset(version)
        self._first = None

    def ins(self, types) -> list[dict]:
        return [t for t in self.txs if t["to_acct"] == self.acct and t["tx_type"] in types]

    def outs(self, types) -> list[dict]:
        return [t for t in self.txs if t["from_acct"] == self.acct and t["tx_type"] in types]

    def first_cp_tx_ids(self) -> set[str]:
        """对手为“首次对手”的交易号（02 规范 2.3：此前与该对手无任何类型、任何方向的交易）。"""
        if self._first is None:
            seen, first = set(), set()
            for t in self.txs:
                cp = t["to_acct"] if t["from_acct"] == self.acct else t["from_acct"]
                if cp not in seen:
                    first.add(t["tx_id"])
                    seen.add(cp)
            self._first = first
        return self._first


def _window(seq: list[dict], i: int, minutes: int) -> list[dict]:
    """seq[i] 起、时间 ≤ seq[i].time + minutes 的交易（seq 已按时间升序）。"""
    t0 = to_min(seq[i]["time"])
    out = []
    for x in seq[i:]:
        if to_min(x["time"]) > t0 + minutes:
            break
        out.append(x)
    return out


def _after(seq: list[dict], t0: int, minutes: int) -> list[dict]:
    """时间在 (t0, t0 + minutes] 内的交易。"""
    return [x for x in seq if t0 < to_min(x["time"]) <= t0 + minutes]


def _total(seq) -> int | float:
    return sum(x["amount"] for x in seq)


def _pct(ratio: float) -> str:
    return f"{ratio * 100:.1f}%"


def _amt(x) -> str:
    return fmt_amount(x)


# ------------------------------------------------------------------ 11 个实现
# 每个函数返回 (证据交易列表, detail, metrics 或 None)，未命中返回 None

def check_fast_in_out(c: Ctx, r: dict):
    p = r["params"]
    W = p["window_min"]
    ins, outs = c.ins(r["in_types"]), c.outs(r["out_types"])
    best = None
    for i in range(len(ins)):
        win_in = _window(ins, i, W)
        win_out = _after(outs, to_min(ins[i]["time"]), W)
        IN, OUT = _total(win_in), _total(win_out)
        if IN >= p["min_amount"] and p["ratio_min"] <= OUT / IN <= p["ratio_max"]:
            if best is None or IN > best[0]:
                best = (IN, OUT, ins[i], win_in + win_out)
    if not best:
        return None
    IN, OUT, a, ev = best
    ratio = OUT / IN
    return ev, (f"{a['time']} 起 {W} 分钟内转入 {_amt(IN)} 元，转出 {_amt(OUT)} 元（{_pct(ratio)}）"), \
        {"in": IN, "out": OUT, "ratio": round(ratio, 3)}


def check_multi_source_in(c: Ctx, r: dict):
    p = r["params"]
    W = p["window_min"]
    ins = c.ins(r["in_types"])
    best = None
    for i in range(len(ins)):
        win = _window(ins, i, W)
        srcs = {x["from_acct"] for x in win} - {CASH}
        if len(srcs) >= p["min_sources"] and (best is None or len(srcs) > len(best[1])):
            best = (ins[i], srcs, win)
    if not best:
        return None
    a, srcs, win = best
    amt = _total(win)
    return win, (f"{a['time']} 起 {W} 分钟内收到 {len(srcs)} 个不同来源的转入（{len(win)} 笔，合计 {_amt(amt)} 元）"), \
        {"sources": len(srcs), "count": len(win), "amount": amt}


def check_split_out(c: Ctx, r: dict):
    p = r["params"]
    W = p["window_min"]
    outs = [x for x in c.outs(r["out_types"]) if x["amount"] <= p["max_single"] and x["to_acct"] != CASH]
    best = None
    for i in range(len(outs)):
        win = _window(outs, i, W)
        recv = {x["to_acct"] for x in win}
        tot = _total(win)
        if len(recv) >= p["min_receivers"] and tot >= p["min_total"] and (best is None or len(recv) > len(best[1])):
            best = (outs[i], recv, win, tot)
    if not best:
        return None
    a, recv, win, tot = best
    return win, (f"{a['time']} 起 {W} 分钟内向 {len(recv)} 个不同账户转出 {len(win)} 笔"
                 f"（每笔不超过 {_amt(p['max_single'])} 元），合计 {_amt(tot)} 元"), \
        {"receivers": len(recv), "count": len(win), "total": tot}


def check_day_clearout(c: Ctx, r: dict):
    p = r["params"]
    ins_d, outs_d = defaultdict(list), defaultdict(list)
    for x in c.ins(r["in_types"]):
        ins_d[x["time"][:10]].append(x)
    for x in c.outs(r["out_types"]):
        outs_d[x["time"][:10]].append(x)
    best = None
    for d in sorted(ins_d):
        IN, OUT = _total(ins_d[d]), _total(outs_d.get(d, []))
        if IN >= p["min_amount"] and p["ratio_min"] <= OUT / IN <= p["ratio_max"]:
            if best is None or IN > best[1]:
                best = (d, IN, OUT)
    if not best:
        return None
    d, IN, OUT = best
    ratio = OUT / IN
    return ins_d[d] + outs_d.get(d, []), f"{d} 转入 {_amt(IN)} 元，转出 {_amt(OUT)} 元（{_pct(ratio)}）", \
        {"in": IN, "out": OUT, "ratio": round(ratio, 3)}


def check_new_account_inflow(c: Ctx, r: dict):
    p = r["params"]
    age = (date.fromisoformat(c.st.start_date) - date.fromisoformat(c.row["open_date"])).days
    if not 0 <= age < p["max_age_days"]:
        return None
    by_day = defaultdict(list)
    for x in c.ins(r["in_types"]):
        by_day[x["time"][:10]].append(x)
    best = None
    for d in sorted(by_day):
        s = _total(by_day[d])
        if s > p["day_in_amount"] and (best is None or s > best[1]):
            best = (d, s)
    if not best:
        return None
    d, s = best
    return by_day[d], f"开户于 {c.row['open_date']}，距数据起始日 {age} 天；{d} 转入 {_amt(s)} 元", \
        {"age_days": age, "day_in": s}


def check_night_large(c: Ctx, r: dict):
    p = r["params"]
    cand = c.ins(r["in_types"]) + c.outs(r["out_types"])
    hits = sorted((x for x in cand if p["hour_from"] <= int(x["time"][11:13]) < p["hour_to"] and x["amount"] > p["amount"]),
                  key=lambda x: (x["time"], x["tx_id"]))
    if not hits:
        return None
    eg = "、".join(f"{x['time']} {'转入' if x['to_acct'] == c.acct else '转出'} {_amt(x['amount'])} 元" for x in hits[:3])
    more = " 等" if len(hits) > 3 else ""
    return hits, (f"{p['hour_from']:02d}:00 至 {p['hour_to'] - 1:02d}:59 有 {len(hits)} 笔单笔超过 "
                  f"{_amt(p['amount'])} 元的转账：{eg}{more}"), {"count": len(hits)}


def check_long_chain(c: Ctx, r: dict):
    p = r["params"]
    cs = trace.chains_of(c.st, c.version, c.acct)
    if not cs:
        return None
    best = max(cs, key=lambda ch: ch["hops"])          # 并列时 max 取第一个，即主链顺序在前者
    if best["hops"] < p["min_hops"]:
        return None
    return best["edges"], f"位于资金链 {best['chain_id']}，该链最长路径 {best['hops']} 跳（不少于 {p['min_hops']} 跳）", \
        {"chain_id": best["chain_id"], "hops": best["hops"]}


def check_first_cp_large(c: Ctx, r: dict):
    p = r["params"]
    first = c.first_cp_tx_ids()
    hits = [x for x in c.ins(r["in_types"]) if x["amount"] > p["amount"] and x["tx_id"] in first]
    if not hits:
        return None
    shown = hits[:c.rs["evidence_limit"]]
    cps = "、".join(x["from_acct"] for x in shown)
    amts = "、".join(_amt(x["amount"]) for x in shown)
    detail = f"首次交易的对手 {cps} 转入 {amts} 元" if len(shown) == 1 else f"首次交易的对手 {cps} 分别转入 {amts} 元"
    return hits, detail, None


def check_salary_income(c: Ctx, r: dict):
    p = r["params"]
    hits = c.ins(r["in_types"])
    if len(hits) < p["min_count"] or not hits:
        return None
    srcs = list(dict.fromkeys(x["from_acct"] for x in hits))
    if len(hits) == 1:
        detail = f"有 1 笔工资入账（{srcs[0]}，{_amt(hits[0]['amount'])} 元）"
    else:
        detail = f"有 {len(hits)} 笔工资入账（{'、'.join(srcs)}，合计 {_amt(_total(hits))} 元）"
    return hits, detail, None


def check_merchant_profile(c: Ctx, r: dict):
    p = r["params"]
    if c.row["acct_type"] != "商户":
        return None
    hits = c.ins(r["in_types"])
    payers = {x["from_acct"] for x in hits} - {CASH}
    if len(payers) < p["min_payers"]:
        return None
    med = statistics.median(x["amount"] for x in hits)
    if med > p["median_max"]:
        return None
    return hits, f"商户账户，{len(hits)} 笔消费转入来自 {len(payers)} 个不同付款方，金额中位数 {_amt(med)} 元", \
        {"payers": len(payers), "count": len(hits), "median": med}


def check_multi_first_cp(c: Ctx, r: dict):
    p = r["params"]
    W = p["window_min"]
    first = c.first_cp_tx_ids()
    cand = [x for x in c.ins(r["in_types"]) if x["tx_id"] in first and x["amount"] > p["amount"]]
    best = None
    for i in range(len(cand)):
        win = _window(cand, i, W)
        cps = list(dict.fromkeys(x["from_acct"] for x in win))
        if len(cps) >= p["min_counterparties"] and (best is None or len(cps) > len(best[1])):
            best = (cand[i], cps, win)
    if not best:
        return None
    a, cps, win = best
    return win, (f"{a['time']} 起 {W} 分钟内有 {len(cps)} 个首次交易的对手各转入超过 {_amt(p['amount'])} 元"
                 f"（{'、'.join(cps[:10])}）"), {"counterparties": len(cps)}


IMPLS = {
    "fast_in_out": check_fast_in_out,
    "multi_source_in": check_multi_source_in,
    "split_out": check_split_out,
    "day_clearout": check_day_clearout,
    "new_account_inflow": check_new_account_inflow,
    "night_large": check_night_large,
    "long_chain": check_long_chain,
    "first_cp_large": check_first_cp_large,
    "salary_income": check_salary_income,
    "merchant_profile": check_merchant_profile,
    "multi_first_cp": check_multi_first_cp,
}


# ------------------------------------------------------------------ 对外
def _evidence_ids(txs: list[dict], limit: int) -> list[str]:
    uniq = {t["tx_id"]: t for t in txs}
    ordered = sorted(uniq.values(), key=lambda t: (t["time"], t["tx_id"]))
    return [t["tx_id"] for t in ordered[:limit]]


def _evaluate(st, version: str, acct_id: str) -> dict:
    rs = load_ruleset(version)
    c = Ctx(st, version, acct_id)
    hits, counter = [], []
    for r in active_rules(rs):
        fn = IMPLS.get(r["impl"])
        if fn is None:
            raise ValueError(f"规则 {r['rule_id']} 的 impl {r['impl']} 未在 core/rules.py 的 IMPLS 中实现")
        res = fn(c, r)
        if res is None:
            continue
        ev, detail, metrics = res
        h = {"rule_id": r["rule_id"], "rule_name": r["name"], "type": r["type"], "level": r["level"],
             "evidence_tx_ids": _evidence_ids(ev, rs["evidence_limit"]), "detail": detail}
        if metrics is not None:
            h["metrics"] = metrics
        (hits if r["type"] == "risk" else counter).append(h)
    return {"acct_id": acct_id, "rule_version": version, "hits": hits, "counter": counter}


def check_rules_result(st, acct_id: str, version: str) -> dict:
    """check_rules 的返回对象（缓存；调用方如需修改请先复制）。参数已由 api 层校验。"""
    return st.cached(("rules", version, acct_id), lambda: _evaluate(st, version, acct_id))
