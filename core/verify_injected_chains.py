"""埋入链路核对脚本（core/verify_injected_chains.py）

逐条核对 gen_data.py 埋入的 12 条链和干扰 D3 是否符合 Data and Rules/gen_profile_v1.yaml：
  1. 答案结构：answer / answer_tx 与交易表一致，链与链不共用账户，EMP_MULES 在 C04、C08 的指定位置
  2. 追链：用 validate_spec.reference_chains 分别按 v1、v2 追链，检出集合须等于 expectations.chain_detected；
     检出的链与答案的交易集合、角色完全一致；除 v2 下的 D3 外，不得出现其他链（背景账户不得上链）
  3. 数值：起始时间、受骗金额与到账间隔、停留时间、转出比例、首跳延迟、每跳间隔与衰减、拆分笔数与金额
  4. 提现、新开户、静默期（含 quiet_scope）、首次对手、D3 三方与第二家企业、R02 防护

这是数据自检工具，会读取答案目录，因此已列入 validate_spec.py --check-leak 的白名单；
规则引擎、工具代码不得 import 本文件。

用法（仓库根目录）：
  python core/verify_injected_chains.py                                   # 默认 data/ 与 eval/
  python core/verify_injected_chains.py --data _tmp_x --answers _tmp_x_eval
退出码：0 全部通过，1 有错误。
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "Data and Rules"
TIME_FMT = "%Y-%m-%d %H:%M"
VICTIM, FIRST, RELAY, SPLIT, TERM = "疑似受骗付款端", "一级收款端", "中转端", "拆分端", "末端"


def load_validator():
    """目录名含空格，不能 import，按路径加载 validate_spec.py。"""
    spec = importlib.util.spec_from_file_location("validate_spec", SPEC / "validate_spec.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_csv(p: Path) -> list[dict]:
    with p.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


class Checker:
    def __init__(self):
        self.errors, self.n_ok = [], 0
        self.section = ""

    def start(self, name):
        self.section = name
        print(f"\n== {name}")

    def check(self, cond, msg):
        if cond:
            self.n_ok += 1
        else:
            self.errors.append(f"[{self.section}] {msg}")
            print(f"  ERROR  {msg}")
        return cond

    def ok(self, msg):
        print(f"  ok     {msg}")


def r02_hits(txs, accts, window, min_sources, types):
    """与 gen_data.r02_like_hits 同口径：闭区间窗口内转入来源去重数 ≥ min_sources。"""
    ev = defaultdict(list)
    for x in txs:
        if x["tx_type"] in types and x["to_acct"] in accts:
            ev[x["to_acct"]].append((x["m"], x["from_acct"]))
    hits = set()
    for a, e in ev.items():
        e.sort()
        j = 0
        for i in range(len(e)):
            while e[i][0] - e[j][0] > window:
                j += 1
            if len({s for _, s in e[j:i + 1]}) >= min_sources:
                hits.add(a)
                break
    return hits


def in_range(x, lohi):
    return lohi[0] <= x <= lohi[1]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="核对埋入链路")
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    ap.add_argument("--answers", type=Path, default=ROOT / "eval", help="答案目录（answer.csv、answer_tx.csv）")
    ap.add_argument("--profile", type=Path, default=SPEC / "gen_profile_v1.yaml")
    a = ap.parse_args(argv)

    vs = load_validator()
    prof = yaml.safe_load(a.profile.read_text(encoding="utf-8"))
    rules = {v: yaml.safe_load((SPEC / "rules" / f"rules_{v}.yaml").read_text(encoding="utf-8")) for v in ("v1", "v2")}
    cash = yaml.safe_load((SPEC / "enums.yaml").read_text(encoding="utf-8"))["special_ids"]["cash"]
    cc = prof["chain_common"]
    cfg = {c["chain_id"]: c for c in prof["chains"]}
    d3cfg = next((d for d in prof.get("distractors", []) if d["id"] == "D3"), None)

    meta = json.loads((a.data / "dataset_meta.json").read_text(encoding="utf-8"))
    t0 = datetime.strptime(meta["time_range"][0], TIME_FMT)
    accounts = read_csv(a.data / "accounts.csv")
    txs = read_csv(a.data / "transactions.csv")
    answer = read_csv(a.answers / "answer.csv")
    answer_tx = read_csv(a.answers / "answer_tx.csv")
    acct = {x["acct_id"]: x for x in accounts}
    for x in txs:
        x["m"] = int((datetime.strptime(x["time"], TIME_FMT) - t0).total_seconds() // 60)
        x["amt"] = float(x["amount"])
    tx_by = {x["tx_id"]: x for x in txs}
    C = Checker()

    def day(m):
        return m // 1440

    def mod(m):
        return m % 1440

    # ------------------------------------------------------------ 1 答案结构
    C.start("答案结构")
    roles = defaultdict(dict)                     # chain_id -> {acct: role}
    pattern = {}
    for r in answer:
        if r["chain_id"]:
            roles[r["chain_id"]][r["acct_id"]] = r["role"]
            pattern[r["chain_id"]] = r["pattern"]
    ctx_tx = defaultdict(list)
    for r in answer_tx:
        ctx_tx[r["chain_id"]].append(tx_by[r["tx_id"]])
    for cid in ctx_tx:
        ctx_tx[cid].sort(key=lambda x: (x["m"], x["tx_id"]))
    C.check(sorted(roles) == sorted(cfg), f"答案中的链 {sorted(roles)} 应为 {sorted(cfg)}")
    owner = defaultdict(list)
    for cid, rs in roles.items():
        for x in rs:
            owner[x].append(cid)
    C.check(all(len(v) == 1 for v in owner.values()), "有账户属于多条链")
    for cid, rs in sorted(roles.items()):
        C.check(pattern[cid] == cfg[cid]["pattern"], f"{cid}: pattern {pattern[cid]} 应为 {cfg[cid]['pattern']}")
        used = set()
        for x in ctx_tx[cid]:
            C.check(x["tx_type"] == "转账" and x["from_acct"] in rs and x["to_acct"] in rs,
                    f"{cid}: answer_tx {x['tx_id']} 不是链上账户之间的转账")
            used |= {x["from_acct"], x["to_acct"]}
        C.check(used == set(rs), f"{cid}: 答案账户与链上交易涉及的账户不一致")
        outside = [x["tx_id"] for x in txs if x["tx_type"] == "转账" and x["from_acct"] in rs and x["to_acct"] in rs
                   and x["tx_id"] not in {y["tx_id"] for y in ctx_tx[cid]}]
        C.check(not outside, f"{cid}: 链上账户之间还有未登记的转账 {outside}")
    # 工资企业 = 发工资笔数最多的企业；EMP_MULES = 领该企业工资的链上账户
    payers = defaultdict(int)
    for x in txs:
        if x["tx_type"] == "工资":
            payers[x["from_acct"]] += 1
    employer = max(sorted(payers), key=lambda k: payers[k])
    employees = {x["to_acct"] for x in txs if x["tx_type"] == "工资" and x["from_acct"] == employer}
    mules = {x: owner[x][0] for x in employees if x in owner}
    C.check(len(mules) == prof["background"]["salary"]["emp_mules"],
            f"领工资的链上账户应为 {prof['background']['salary']['emp_mules']} 个，实际 {mules}")
    for cid, c in cfg.items():
        if c.get("first_receiver_from"):
            fr = [x for x, r in roles[cid].items() if r == FIRST]
            C.check(len(fr) == 1 and fr[0] in mules, f"{cid}: 一级收款端应为 EMP_MULES（{c['first_receiver_from']}）")
    C.ok(f"{len(roles)} 条链，{sum(len(v) for v in roles.values())} 个链上账户，{len(answer_tx)} 笔链上转账；"
         f"EMP_MULES {', '.join(f'{k}@{v}' for k, v in sorted(mules.items()))}")

    # ------------------------------------------------------------ 2 追链（参考实现）
    d3_parties = [r["acct_id"] for r in answer if r["pattern"] == (d3cfg or {}).get("pattern")]
    detected = {}
    for ver in ("v1", "v2"):
        C.start(f"追链 {ver}")
        ref = vs.reference_chains(acct, txs, rules[ver])
        expect = set(prof["expectations"]["chain_detected"][ver])
        got, matched = set(), set()
        for cid in sorted(cfg):
            want = {x["tx_id"] for x in ctx_tx[cid]}
            hit = [ch for ch in ref if set(ch["tx_ids"]) & want]
            exact = [ch for ch in hit if set(ch["tx_ids"]) == want]
            C.check(len(hit) == len(exact), f"{cid}: 只被部分追到，或与其他交易拼在一起 {[h['chain_id'] for h in hit]}")
            if exact:
                ch = exact[0]
                got.add(cid)
                matched.add(ch["chain_id"])
                C.check(ch["roles"] == roles[cid], f"{cid}: 参考实现角色 {ch['roles']} 与答案 {roles[cid]} 不一致")
                hops = cfg[cid].get("layers", 1) + 1
                C.check(ch["hops"] == hops, f"{cid}: hops={ch['hops']}，应为 {hops}")
                detected.setdefault(cid, {})[ver] = ch
        C.check(got == expect, f"检出 {sorted(got)}，预期 {sorted(expect)}")
        extra = [ch for ch in ref if ch["chain_id"] not in matched]
        d3_chain = [ch for ch in extra if set(ch["accounts"]) == set(d3_parties)]
        for ch in extra:
            if ch in d3_chain:
                continue
            C.check(False, f"多出的链 {ch['chain_id']}：账户 {ch['accounts']}（背景账户不得上链）")
        if d3cfg:
            w = vs.resolve_window(rules[ver])
            a_, b_ = d3cfg["transfers"]
            gap = hhmm(b_["time"][11:]) - hhmm(a_["time"][11:])
            want_d3 = gap <= w
            C.check(bool(d3_chain) == want_d3, f"D3 在 {ver} 下{'应' if want_d3 else '不应'}成链（间隔 {gap}，窗口 {w}）")
            if d3_chain:
                rl = d3_chain[0]["roles"]
                C.check(sorted(rl.values()) == sorted([VICTIM, FIRST, TERM]), f"D3 角色 {rl}")
        C.ok(f"参考实现 {len(ref)} 条链；检出答案链 {len(got)} 条" + ("；D3 成链" if d3_chain else ""))

    # ------------------------------------------------------------ 3 数值
    C.start("时间与金额")
    lo_v, hi_v = cc["victim_amount"]
    rows = []
    for cid in sorted(cfg):
        c, rs, ts = cfg[cid], roles[cid], ctx_tx[cid]
        victims = [x for x in ts if rs[x["from_acct"]] == VICTIM]
        total = sum(x["amt"] for x in victims)
        last_in = max(x["m"] for x in victims)
        d = day(ts[0]["m"])
        C.check(all(day(x["m"]) == d for x in ts), f"{cid}: 链路跨越自然日")
        C.check(all(in_range(x["amt"], cc["victim_amount"]) for x in victims), f"{cid}: 受骗金额越界")
        C.check(last_in - min(x["m"] for x in victims) <= cc["inflow_spread_max_min"], f"{cid}: 受骗入账间隔过大")
        C.check(in_range(len(victims), (c["victims"], c["victims"]) if isinstance(c["victims"], int) else c["victims"]),
                f"{cid}: 受骗方人数 {len(victims)}")
        start = mod(ts[0]["m"])
        if "start_window" in c:
            C.check(hhmm(c["start_window"][0]) <= start <= hhmm(c["start_window"][1]), f"{cid}: 首笔 {ts[0]['time']} 不在 start_window")
        else:
            C.check(cc["start_hour"][0] * 60 <= start < cc["start_hour"][1] * 60, f"{cid}: 首笔 {ts[0]['time']} 不在 start_hour")
        if c.get("all_transfers_before"):
            C.check(all(mod(x["m"]) < hhmm(c["all_transfers_before"]) for x in ts),
                    f"{cid}: 转账未在 {c['all_transfers_before']} 前结束")
        outs = [x for x in ts if rs[x["from_acct"]] != VICTIM]
        detail = ""
        if c["pattern"] == "快进快出":
            C.check(len(outs) == 1, f"{cid}: 一级收款端应只有 1 笔转出")
            o = outs[0]
            dwell, ratio = o["m"] - last_in, o["amt"] / total
            C.check(in_range(dwell, c["dwell_min"]), f"{cid}: 停留 {dwell} 分钟不在 {c['dwell_min']}")
            C.check(in_range(ratio, c["out_ratio"]), f"{cid}: 转出比例 {ratio:.4f} 不在 {c['out_ratio']}")
            detail = f"停留 {dwell}′，比例 {ratio:.3f}"
        elif c["pattern"] == "分层中转":
            C.check(in_range(total, c["total"]), f"{cid}: 合计 {total} 不在 {c['total']}")
            C.check(len(outs) == c["layers"], f"{cid}: 层间转账 {len(outs)} 笔，应为 {c['layers']}")
            path = [x for x in rs if rs[x] == FIRST]
            prev_t, prev_a = last_in, total
            gaps, ratios = [], []
            for i, o in enumerate(outs):
                C.check(o["from_acct"] == path[-1], f"{cid}: 第 {i + 1} 跳不是从上一层转出")
                path.append(o["to_acct"])
                gap = o["m"] - prev_t
                C.check(in_range(gap, c["first_hop_delay_min"] if i == 0 else c["hop_gap_min"]), f"{cid}: 第 {i + 1} 跳间隔 {gap}")
                r = o["amt"] / prev_a
                C.check(1 - c["hop_decay"][1] - 1e-9 <= r <= 1 - c["hop_decay"][0], f"{cid}: 第 {i + 1} 跳比例 {r:.4f}")
                gaps.append(gap)
                ratios.append(r)
                prev_t, prev_a = o["m"], o["amt"]
            C.check([rs[x] for x in path] == [FIRST] + [RELAY] * (c["layers"] - 1) + [TERM], f"{cid}: 层级角色 {path}")
            for lvl, ref in (c.get("relay_from") or {}).items():
                C.check(path[int(lvl[1:]) - 1] in mules, f"{cid}: {lvl} 应为 {ref}")
            detail = f"间隔 {gaps}′，最低比例 {min(ratios):.3f}"
        else:
            C.check(in_range(total, c["total"]), f"{cid}: 合计 {total} 不在 {c['total']}")
            S = sum(x["amt"] for x in outs)
            recv = [x["to_acct"] for x in outs]
            C.check(in_range(len(outs), c["parts"]), f"{cid}: 拆分 {len(outs)} 笔不在 {c['parts']}")
            C.check(len(set(recv)) == len(recv) and all(rs[x] == TERM for x in recv), f"{cid}: 收款方重复或角色不是末端")
            C.check(all(in_range(x["amt"], c["part_amount"]) for x in outs), f"{cid}: 单笔越界 {[x['amt'] for x in outs]}")
            C.check(in_range(S / total, c["part_sum_ratio"]), f"{cid}: 拆分合计比例 {S / total:.4f}")
            delay, spread = outs[0]["m"] - last_in, outs[-1]["m"] - outs[0]["m"]
            C.check(in_range(delay, c["split_delay_min"]), f"{cid}: 首笔拆分延迟 {delay}")
            C.check(in_range(spread, c["split_spread_min"]), f"{cid}: 拆分跨度 {spread}")
            detail = f"{len(outs)} 笔，延迟 {delay}′，跨度 {spread}′，比例 {S / total:.3f}"
        rows.append((cid, c["pattern"], ts[0]["time"], len(rs), len(ts), int(total), detail))
    C.ok("各链参数均在 profile 范围内")

    # ------------------------------------------------------------ 4 提现
    C.start("提现")
    terms = [(cid, x) for cid in sorted(cfg) for x, r in roles[cid].items() if r == TERM]
    wd = [x for x in txs if x["tx_type"] == "提现"]
    C.check(len(wd) == round(cc["terminal_withdraw_ratio"] * len(terms)),
            f"提现 {len(wd)} 笔，应为 round({cc['terminal_withdraw_ratio']} × {len(terms)})")
    term_chain = dict((x, cid) for cid, x in terms)
    for w in wd:
        cid = term_chain.get(w["from_acct"])
        if not C.check(cid is not None and w["to_acct"] == cash, f"{w['tx_id']}: 提现方不是末端或收款方不是 {cash}"):
            continue
        ins = [x for x in ctx_tx[cid] if x["to_acct"] == w["from_acct"]]
        got_amt, t_in = sum(x["amt"] for x in ins), max(x["m"] for x in ins)
        C.check(in_range(w["amt"] / got_amt, cc["withdraw_amount_ratio"]), f"{w['tx_id']}: 提现比例 {w['amt'] / got_amt:.3f}")
        C.check(in_range(w["m"] - t_in, cc["withdraw_delay_min"]), f"{w['tx_id']}: 提现延迟 {w['m'] - t_in}")
        C.check(day(w["m"]) == day(t_in), f"{w['tx_id']}: 提现跨日")
    C.ok(f"末端 {len(terms)} 个，提现 {len(wd)} 笔")

    # ------------------------------------------------------------ 5 新开户
    C.start("新开户")
    d0 = date.fromisoformat(meta["time_range"][0][:10])
    slots = [x for cid in sorted(cfg) for x, r in roles[cid].items() if r in (FIRST, RELAY, SPLIT) and x not in mules]
    lo_d, hi_d = cc["new_account_open_days_before"]
    new = [x for x in acct if acct[x]["open_date"] > prof["accounts"]["normal_open_date"][1]]
    C.check(set(new) <= set(slots), f"新开户不在合格槽位中：{sorted(set(new) - set(slots))}")
    C.check(len(new) == round(cc["intermediate_new_account_ratio"] * len(slots)),
            f"新开户 {len(new)} 个，应为 round({cc['intermediate_new_account_ratio']} × {len(slots)})")
    for x in new:
        age = (d0 - date.fromisoformat(acct[x]["open_date"])).days
        C.check(lo_d <= age <= hi_d, f"{x}: 开户距起始日 {age} 天")
    C.ok(f"合格槽位 {len(slots)} 个（EMP_MULES 除外），新开户 {len(new)} 个")

    # ------------------------------------------------------------ 6 静默期与首次对手
    C.start("静默期与首次对手")
    natural = cc.get("quiet_scope") == "natural_day"
    groups = [(cid, cc["quiet_margin_min"], ctx_tx[cid] + [w for w in wd if term_chain.get(w["from_acct"]) == cid])
              for cid in sorted(cfg)]
    d3_tx = []
    if d3cfg and d3_parties:
        d3_tx = sorted((x for x in txs if x["tx_type"] == "转账" and x["from_acct"] in d3_parties
                        and x["to_acct"] in d3_parties), key=lambda x: x["m"])
        groups.append(("D3", d3cfg.get("quiet_margin_min", cc["quiet_margin_min"]), d3_tx))
    n_q = 0
    for gid, margin, ts in groups:
        own = {x["tx_id"] for x in ts}
        lo, hi = min(x["m"] for x in ts) - margin, max(x["m"] for x in ts) + margin
        if natural:
            dd = day(ts[0]["m"])
            lo, hi = min(lo, dd * 1440), max(hi, dd * 1440 + 1439)
        members = {x["from_acct"] for x in ts} | {x["to_acct"] for x in ts if x["to_acct"] != cash}
        bad = [x["tx_id"] for x in txs if x["tx_type"] == "转账" and x["tx_id"] not in own and lo <= x["m"] <= hi
               and (x["from_acct"] in members or x["to_acct"] in members)]
        C.check(not bad, f"{gid}: 静默期内有其他转账 {bad[:5]}")
        pairs = {frozenset((x, y)) for x in members for y in members if x < y}
        pairs |= {frozenset((x["from_acct"], x["to_acct"])) for x in ts if x["to_acct"] != cash}
        dup = [x["tx_id"] for x in txs if frozenset((x["from_acct"], x["to_acct"])) in pairs and x["tx_id"] not in own]
        C.check(not dup, f"{gid}: 链上账户之间另有交易 {dup[:5]}（违反首次对手）")
        n_q += len(members)
    C.ok(f"{len(groups)} 组、{n_q} 个账户；静默范围 = 前后 {cc['quiet_margin_min']} 分钟" + (" ∪ 整个自然日" if natural else ""))

    # ------------------------------------------------------------ 7 D3
    if d3cfg:
        C.start("D3 合租转发")
        C.check(len(d3_parties) == 3, f"答案中合租转发账户 {d3_parties}")
        want = [(x["time"], x["amount"]) for x in d3cfg["transfers"]]
        C.check([(x["time"], x["amt"]) for x in d3_tx] == want, f"D3 转账 {[(x['time'], x['amt']) for x in d3_tx]} 应为 {want}")
        if len(d3_tx) == 2:
            f, p, l_ = d3_tx[0]["from_acct"], d3_tx[0]["to_acct"], d3_tx[1]["to_acct"]
            C.check(d3_tx[1]["from_acct"] == p, "D3 第二笔应由 P 转出")
            C.check(all(acct[x]["acct_type"] == "个人" for x in (f, p, l_)), "D3 三方应为个人")
            sal = [x for x in txs if x["tx_type"] == "工资" and x["to_acct"] == p]
            emp2 = sal[0]["from_acct"] if len(sal) == 1 else None
            C.check(emp2 and emp2 != employer and sal[0]["time"] == d3cfg["salary"]["time"]
                    and in_range(sal[0]["amt"], d3cfg["salary"]["amount"]), f"P 的工资 {[(x['from_acct'], x['time'], x['amt']) for x in sal]}")
            C.check(any(r["acct_id"] == emp2 and r["pattern"] == "工资" for r in answer), "第二家企业未登记为 工资")
            C.check(payers.get(emp2) == 1, "第二家企业应只发 1 笔工资")
            C.check(not ({f, p, l_} & employees), "D3 三方不应是工资企业的员工")
            dd = day(d3_tx[0]["m"])
            p_in = sum(x["amt"] for x in txs if x["tx_type"] == "转账" and x["to_acct"] == p and day(x["m"]) == dd)
            p_out = sum(x["amt"] for x in txs if x["tx_type"] == "转账" and x["from_acct"] == p and day(x["m"]) == dd)
            r04 = vs.rule_by_id(rules["v1"], "R04")["params"]
            r01 = vs.rule_by_id(rules["v2"], "R01")["params"]
            ratio = p_out / p_in
            C.check(r01["ratio_min"] <= ratio < r04["ratio_min"], f"P 当日出入比 {ratio:.3f} 应在 [R01 {r01['ratio_min']}, R04 {r04['ratio_min']})")
            C.ok(f"F={f} P={p} L={l_}，第二家企业 {emp2}，P 当日出入比 {ratio:.3f}")

    # ------------------------------------------------------------ 8 R02 防护与预期触发
    C.start("R02（背景转入）")
    r02 = vs.rule_by_id(rules["v1"], "R02")
    pr = r02["params"]
    v1_set = set(prof["expectations"]["chain_detected"]["v1"])
    guarded = [x for cid in sorted(cfg) if cid not in v1_set for x, r in roles[cid].items() if r == VICTIM] + d3_parties
    hits = r02_hits(txs, set(acct), pr["window_min"], pr["min_sources"], set(r02["in_types"]))
    C.check(not (hits & set(guarded)), f"应保持干净的账户命中 R02：{sorted(hits & set(guarded))}")
    for cid, c in cfg.items():
        if "R02" in str(c.get("note", "")):
            fr = [x for x, r in roles[cid].items() if r == FIRST]
            C.check(bool(fr) and fr[0] in hits, f"{cid}: 一级收款端应命中 R02")
    persons = sorted(x for x in hits if acct[x]["acct_type"] == "个人")
    on_chain = [x for x in persons if x in owner]
    C.ok(f"防护账户 {len(guarded)} 个均未命中；命中 R02 的个人 {len(persons)} 个（其中链上 {len(on_chain)} 个：{on_chain}）")

    # ------------------------------------------------------------ 汇总
    print("\n== 汇总")
    print(f"  {'链':<4}{'模式':<6}{'首笔':<18}{'账户':>4}{'转账':>4}{'受骗合计':>9}  v1 v2  细节")
    for cid, pat, t, na, nt, tot, det in rows:
        mark = lambda v: " Y " if v in detected.get(cid, {}) else " - "
        print(f"  {cid:<4}{pat:<6}{t:<18}{na:>4}{nt:>4}{tot:>9}  {mark('v1')}{mark('v2')} {det}")
    print(f"\n结果：{C.n_ok} 项通过，{len(C.errors)} 个错误")
    return 1 if C.errors else 0


if __name__ == "__main__":
    sys.exit(main())
