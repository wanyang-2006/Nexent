"""按 Data and Rules/gen_profile_v1.yaml 生成仿真交易数据（core/gen_data.py）。

阶段（--stage，默认 full）：
  background：账户、涉案候选池、个人互转、消费、工资。只写 data/。
  full：plan_chains 先抽好 12 条链与 D3 的蓝图并登记约束，再生成背景，
        然后 write_plan 照蓝图写入，并写 eval/answer.csv、eval/answer_tx.csv。

用法（仓库根目录）：
  python -m core.gen_data --force                    # 生成正式数据到 data/ 与 eval/（已有数据时须 --force）
  python -m core.gen_data --out tmp_a --eval-out tmp_a_eval   # 输出到其他目录（自测用）
  python -m core.gen_data --stage background --out tmp_bg     # 只生成背景（第 1 天口径）
  python "Data and Rules/validate_spec.py" --skip-spec --data data --eval eval
  python core/verify_injected_chains.py              # 逐条核对埋入链路

约定（01_数据规范.md）：
  - 所有参数取自 profile，代码不写死数值；所有随机量只来自 random.Random(seed)，不遍历无序集合。
  - CSV 为 UTF-8 无 BOM、LF 换行；交易按 (time, 生成顺序) 排序后统一编号 T00001...
  - dataset_meta.json 不含生成时间和任何答案信息，保证同 seed 两次生成的文件 sha256 相同。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "Data and Rules"
DEFAULT_PROFILE = SPEC / "gen_profile_v1.yaml"
TIME_FMT = "%Y-%m-%d %H:%M"
ACCT_COLS = ["acct_id", "name", "acct_type", "open_date"]
TX_COLS = ["tx_id", "time", "from_acct", "to_acct", "amount", "tx_type"]
MAX_TRIES = 10000


# ---------------------------------------------------------------- 数据结构
@dataclass
class Reservations:
    """埋链前登记的约束，背景交易生成时必须避开（background 阶段为空）。

    quiet:     账户 -> 若干闭区间 [lo, hi]（距数据起点的分钟数），区间内该账户不得有背景“转账”
               （chain_common.quiet_margin_min + quiet_scope）
    no_pair:   不得有任何背景交易往来的账户对（chain_common.fresh_counterparty）
    src_guard: 账户 -> 已接受的背景转入 [(t, 来源)]；新转入若使任意 guard_window 分钟内来源数
               ≥ guard_min_sources（即凑成 R02）则拒绝（chain_common.r02_guard）
    """
    quiet: dict[str, list[tuple[int, int]]] = field(default_factory=dict)
    no_pair: set[frozenset[str]] = field(default_factory=set)
    src_guard: dict[str, list[tuple[int, str]]] = field(default_factory=dict)
    guard_window: int = 0
    guard_min_sources: int = 0

    def add_quiet(self, acct: str, lo: int, hi: int) -> None:
        self.quiet.setdefault(acct, []).append((lo, hi))

    def add_no_pair(self, a: str, b: str) -> None:
        self.no_pair.add(frozenset((a, b)))

    def add_src_guard(self, acct: str) -> None:
        self.src_guard.setdefault(acct, [])

    def blocks_transfer(self, a: str, b: str, t: int) -> bool:
        """a→b 在 t 时刻的背景转账是否违反约束。"""
        if frozenset((a, b)) in self.no_pair:
            return True
        if any(lo <= t <= hi for x in (a, b) for lo, hi in self.quiet.get(x, ())):
            return True
        return b in self.src_guard and self._concentrates(b, a, t)

    def blocks_pair(self, a: str, b: str) -> bool:
        return frozenset((a, b)) in self.no_pair

    def note_transfer(self, a: str, b: str, t: int) -> None:
        """背景转账被接受后调用，供 src_guard 累计。"""
        if b in self.src_guard:
            self.src_guard[b].append((t, a))

    def _concentrates(self, acct: str, src: str, t: int) -> bool:
        w = self.guard_window
        ev = sorted([x for x in self.src_guard[acct] if abs(x[0] - t) <= w] + [(t, src)])
        j = 0
        for i in range(len(ev)):                                # 与 r02_like_hits 同口径（闭区间，偏保守）
            while ev[i][0] - ev[j][0] > w:
                j += 1
            if len({s for _, s in ev[j:i + 1]}) >= self.guard_min_sources:
                return True
        return False


@dataclass
class Ctx:
    prof: dict
    seed: int
    rng: random.Random
    t0: datetime                      # 数据起点（time_range[0]）
    t_end: int                        # 数据终点，距起点的分钟数
    days: int
    accounts: list[dict] = field(default_factory=list)          # acct_id, name, acct_type, open_date
    by_type: dict[str, list[str]] = field(default_factory=dict)
    pool: list[str] = field(default_factory=list)               # 涉案候选池（抽取顺序即随机顺序）
    emp_mules: list[str] = field(default_factory=list)          # 领工资的候选池账户：[0]→C04 一级收款端，[1]→C08 L2
    employer: str | None = None
    employees: list[str] = field(default_factory=list)
    second_employer: str | None = None                          # D3：只给 P 发 1 笔工资的企业（gen_salary 排除它）
    d3_parties: list[str] = field(default_factory=list)         # D3：F、P、L（池外个人，gen_salary 排除）
    hf_merchants: list[str] = field(default_factory=list)
    normal_merchants: list[str] = field(default_factory=list)
    txs: list[dict] = field(default_factory=list)               # t(分钟), from, to, amount, tx_type, seq
    res: Reservations = field(default_factory=Reservations)
    answer: list[dict] = field(default_factory=list)            # full：acct_id, chain_id, pattern, role
    answer_tx: list[tuple[int, str]] = field(default_factory=list)  # full：(交易 seq, chain_id)

    def add_tx(self, t: int, f: str, to: str, amount: int, tx_type: str) -> int:
        if not 0 <= t <= self.t_end:
            raise ValueError(f"交易时间超出数据范围：{t}")
        if f == to:
            raise ValueError(f"自转：{f}")
        seq = len(self.txs)
        self.txs.append({"t": t, "from": f, "to": to, "amount": int(amount), "tx_type": tx_type, "seq": seq})
        return seq

    def minute(self, s: str) -> int:
        return int((datetime.strptime(s, TIME_FMT) - self.t0).total_seconds() // 60)

    def fmt(self, t: int) -> str:
        return (self.t0 + timedelta(minutes=t)).strftime(TIME_FMT)


# ---------------------------------------------------------------- 工具函数
def load_profile(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def rand_minute_in_hours(rng: random.Random, day: int, hours: list[int]) -> int:
    """hours=[8, 22] 表示 08:00~21:59。"""
    return day * 1440 + rng.randint(hours[0] * 60, hours[1] * 60 - 1)


def rand_date(rng: random.Random, lo: str, hi: str) -> str:
    d0, d1 = date.fromisoformat(lo), date.fromisoformat(hi)
    return (d0 + timedelta(days=rng.randint(0, (d1 - d0).days))).isoformat()


def new_ctx(prof: dict, seed: int) -> Ctx:
    lo, hi = prof["time_range"]
    t0 = datetime.strptime(lo, TIME_FMT)
    t1 = datetime.strptime(hi, TIME_FMT)
    return Ctx(prof=prof, seed=seed, rng=random.Random(seed), t0=t0,
               t_end=int((t1 - t0).total_seconds() // 60), days=(t1.date() - t0.date()).days + 1)


# ---------------------------------------------------------------- 第 1 天：背景数据
def gen_accounts(ctx: Ctx) -> None:
    cfg = ctx.prof["accounts"]
    types = [t for t, n in cfg["counts"].items() for _ in range(n)]
    if cfg.get("id_assignment") == "shuffled":
        ctx.rng.shuffle(types)
    seq = defaultdict(int)
    ctx.by_type = {t: [] for t in cfg["counts"]}
    for i, t in enumerate(types, 1):
        acct_id = f"A{i:04d}"
        seq[t] += 1
        ctx.accounts.append({"acct_id": acct_id, "name": cfg["name_format"][t].format(n=seq[t]),
                             "acct_type": t, "open_date": rand_date(ctx.rng, *cfg["normal_open_date"])})
        ctx.by_type[t].append(acct_id)


def pick_pool(ctx: Ctx) -> None:
    """抽涉案候选池，并从中抽 EMP_MULES（在 plan_chains 之前确定，第 2 天埋链才能用上）。"""
    n = ctx.prof["accounts"]["suspect_pool_size"]
    ctx.pool = ctx.rng.sample(ctx.by_type["个人"], n)
    ctx.emp_mules = ctx.rng.sample(ctx.pool, ctx.prof["background"]["salary"]["emp_mules"])


def gen_personal_transfers(ctx: Ctx) -> None:
    cfg = ctx.prof["background"]["personal_transfer"]
    persons, rng = ctx.by_type["个人"], ctx.rng
    for _ in range(cfg["count"]):
        for _try in range(MAX_TRIES):
            f, to = rng.sample(persons, 2)                     # 均匀随机，不自转
            t = rand_minute_in_hours(rng, rng.randrange(ctx.days), cfg["hours"])
            amount = rng.randint(*cfg["amount"])
            if not ctx.res.blocks_transfer(f, to, t):
                break
        else:
            raise RuntimeError("个人互转无法避开埋链约束，请检查 Reservations 是否过多")
        ctx.add_tx(t, f, to, amount, cfg["tx_type"])
        ctx.res.note_transfer(f, to, t)


def gen_consumption(ctx: Ctx) -> None:
    bg, rng, persons = ctx.prof["background"], ctx.rng, ctx.by_type["个人"]
    hf, nm = bg["high_freq_merchants"], bg["normal_merchants"]
    merchants = ctx.by_type["商户"]
    if hf["count"] + nm["count"] != len(merchants):
        raise ValueError("高频商户数 + 普通商户数 应等于商户总数")
    ctx.hf_merchants = rng.sample(merchants, hf["count"])
    hf_set = set(ctx.hf_merchants)
    ctx.normal_merchants = [m for m in merchants if m not in hf_set]

    for m in ctx.hf_merchants:                                  # 高频商户：每天 30~34 笔，同日付款方不重复
        for day in range(ctx.days):
            n = rng.randint(*hf["per_day"])
            payers = rng.sample(persons, n) if hf.get("distinct_payers_per_day") else [rng.choice(persons) for _ in range(n)]
            for p in payers:
                ctx.add_tx(rand_minute_in_hours(rng, day, hf["hours"]), p, m, rng.randint(*hf["amount"]), hf["tx_type"])

    for m in ctx.normal_merchants:                              # 普通商户：每周 10~20 笔，付款方不重复
        n = max(1, round(rng.randint(*nm["per_week"]) * ctx.days / 7))
        payers = rng.sample(persons, n) if nm.get("distinct_payers") else [rng.choice(persons) for _ in range(n)]
        for p in payers:
            t = rand_minute_in_hours(rng, rng.randrange(ctx.days), nm["hours"])
            ctx.add_tx(t, p, m, rng.randint(*nm["amount"]), nm["tx_type"])


def gen_salary(ctx: Ctx) -> None:
    """工资企业从“除 D3 第二家企业外”的企业中抽；员工 = 2 名 EMP_MULES + 池外个人（排除 D3 三方）。
    background 阶段 second_employer、d3_parties 为空，结果与第 1 天相同。"""
    cfg, rng = ctx.prof["background"]["salary"], ctx.rng
    if cfg["employer_count"] != 1:
        raise NotImplementedError("v1 只支持 1 家工资企业")
    ctx.employer = rng.choice([c for c in ctx.by_type["企业"] if c != ctx.second_employer])
    excluded = set(ctx.pool) | set(ctx.d3_parties)
    others = [p for p in ctx.by_type["个人"] if p not in excluded]
    ctx.employees = ctx.emp_mules + rng.sample(others, cfg["employees"] - cfg["emp_mules"])
    rng.shuffle(ctx.employees)
    lo, hi = (ctx.minute(s) for s in cfg["time"])
    for e in ctx.employees:
        if ctx.res.blocks_pair(ctx.employer, e):
            raise RuntimeError(f"工资 {ctx.employer}→{e} 与埋链约束冲突")
        ctx.add_tx(rng.randint(lo, hi), ctx.employer, e, rng.randint(*cfg["amount"]), cfg["tx_type"])


def gen_background(ctx: Ctx) -> None:
    gen_personal_transfers(ctx)
    gen_consumption(ctx)
    gen_salary(ctx)


# ---------------------------------------------------------------- 第 2 天：埋链与干扰（蓝图模式）
# 顺序：gen_accounts → pick_pool → plan_chains → gen_background → write_plan × N → finalize。
# plan_chains 一次性抽好每条链的全部细节（账户、每笔时间与金额、提现、新开户），并登记 Reservations；
# write_plan 只照蓝图写交易和答案，不再抽随机数。plan_chains 必须在 gen_background 之前，背景才能避开约束。
# ctx.emp_mules 已在 pick_pool 中确定：[0] 用作 C04 一级收款端，[1] 用作 C08 的 L2；其余角色从 pool 中不放回抽取。
TX_TRANSFER, TX_WITHDRAW = "转账", "提现"
ROLE_VICTIM, ROLE_FIRST, ROLE_RELAY, ROLE_SPLIT, ROLE_TERM = "疑似受骗付款端", "一级收款端", "中转端", "拆分端", "末端"
ROLE_ORDER = [ROLE_VICTIM, ROLE_FIRST, ROLE_RELAY, ROLE_SPLIT, ROLE_TERM]
BENIGN_ORDER = ["工资", "商户", "合租转发"]
MULE_REF = re.compile(r"^EMP_MULES\[(\d+)\]$")


def hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def _tx(t: int, f: str, to: str, amount: int, tx_type: str = TX_TRANSFER) -> dict:
    return {"t": t, "from": f, "to": to, "amount": int(amount), "tx_type": tx_type}


def _count(v) -> tuple[int, int]:
    """victims 可写成整数或 [lo, hi]。"""
    return (v, v) if isinstance(v, int) else (v[0], v[1])


def _split_sum(rng: random.Random, total: int, n: int, lo: int, hi: int) -> list[int]:
    """把 total 拆成 n 个 [lo, hi] 内的整数（顺序随机）。调用方保证 n*lo ≤ total ≤ n*hi。"""
    if not n * lo <= total <= n * hi:
        raise ValueError(f"无法把 {total} 拆成 {n} 个 [{lo}, {hi}] 内的整数")
    out, rest = [], total
    for i in range(n - 1):
        left = n - i - 1
        a = rng.randint(max(lo, rest - left * hi), min(hi, rest - left * lo))
        out.append(a)
        rest -= a
    out.append(rest)
    rng.shuffle(out)
    return out


class _Picker:
    """候选池账户的不放回抽取；EMP_MULES[i] 按引用直接取。"""

    def __init__(self, ctx: Ctx):
        mules = set(ctx.emp_mules)
        self.avail = [p for p in ctx.pool if p not in mules]      # ctx.pool 本身是随机顺序
        self.mules = ctx.emp_mules

    def take(self, ref: str | None = None) -> str:
        if ref:
            m = MULE_REF.match(ref)
            if not m:
                raise ValueError(f"无法解析账户引用 {ref}")
            return self.mules[int(m.group(1))]
        if not self.avail:
            raise RuntimeError("候选池账户不足，请调大 suspect_pool_size")
        return self.avail.pop(0)


def _new_plan(c: dict, day: int) -> dict:
    return {"chain_id": c["chain_id"], "pattern": c["pattern"], "day": day, "txs": [], "rows": [],
            "new_slots": [], "terminals": [], "transfers_before": c.get("all_transfers_before")}


def _role(plan: dict, acct: str, role: str) -> None:
    plan["rows"].append({"acct_id": acct, "chain_id": plan["chain_id"], "pattern": plan["pattern"], "role": role})


def _start(ctx: Ctx, c: dict, cc: dict, day: int) -> int:
    """链路首笔时间：一般为 start_hour（左闭右开）；C03 为 start_window（两端都含）。"""
    if "start_window" in c:
        lo, hi = (hhmm(s) for s in c["start_window"])
        return day * 1440 + ctx.rng.randint(lo, hi)
    return rand_minute_in_hours(ctx.rng, day, cc["start_hour"])


def _inflows(ctx: Ctx, cc: dict, plan: dict, victims: list[str], amounts: list[int], to: str, start: int) -> int:
    """受骗方转入：首笔在 start，其余在之后 1~inflow_spread_max_min 分钟内（分钟互不相同）。返回最后一笔时间。"""
    spread = cc["inflow_spread_max_min"]
    offs = [0] + sorted(ctx.rng.sample(range(1, spread + 1), len(victims) - 1))
    for v, o, a in zip(victims, offs, amounts):
        plan["txs"].append(_tx(start + o, v, to, a))
        _role(plan, v, ROLE_VICTIM)
    return start + offs[-1]


def plan_ffio(ctx: Ctx, c: dict, cc: dict, day: int, pick: _Picker) -> dict:
    """快进快出 C01~C06：受骗方 → A → 末端 E。停留时间从最后一笔转入算起。"""
    rng, plan = ctx.rng, _new_plan(c, day)
    victims = [pick.take() for _ in range(_count(c["victims"])[0])]
    a, e = pick.take(c.get("first_receiver_from")), pick.take()
    amounts = [rng.randint(*cc["victim_amount"]) for _ in victims]
    last_in = _inflows(ctx, cc, plan, victims, amounts, a, _start(ctx, c, cc, day))
    total = sum(amounts)
    out = rng.randint(math.ceil(total * c["out_ratio"][0]), math.floor(total * c["out_ratio"][1]))
    plan["txs"].append(_tx(last_in + rng.randint(*c["dwell_min"]), a, e, out))
    _role(plan, a, ROLE_FIRST)
    _role(plan, e, ROLE_TERM)
    plan["new_slots"], plan["terminals"] = [a], [e]
    return plan


def plan_layered(ctx: Ctx, c: dict, cc: dict, day: int, pick: _Picker) -> dict:
    """分层中转 C07~C09：受骗方 → L1 → L2 → L3 → 末端。首跳从最后一笔转入算起，每跳金额衰减 hop_decay。"""
    rng, plan = ctx.rng, _new_plan(c, day)
    for _ in range(MAX_TRIES):
        amounts = [rng.randint(*cc["victim_amount"]) for _ in range(rng.randint(*_count(c["victims"])))]
        if c["total"][0] <= sum(amounts) <= c["total"][1]:
            break
    else:
        raise RuntimeError(f"{c['chain_id']}: 抽不到满足 total 的受骗金额")
    victims = [pick.take() for _ in amounts]
    relay_from = c.get("relay_from") or {}
    layers = [pick.take(relay_from.get(f"L{i}")) for i in range(1, c["layers"] + 1)]
    e = pick.take()
    last_in = _inflows(ctx, cc, plan, victims, amounts, layers[0], _start(ctx, c, cc, day))
    path, t, amt = layers + [e], last_in + rng.randint(*c["first_hop_delay_min"]), sum(amounts)
    d_lo, d_hi = c["hop_decay"]
    for i in range(len(layers)):
        if i:
            t += rng.randint(*c["hop_gap_min"])
        amt = rng.randint(math.ceil(amt * (1 - d_hi)), math.floor(amt * (1 - d_lo)))
        plan["txs"].append(_tx(t, path[i], path[i + 1], amt))
    _role(plan, layers[0], ROLE_FIRST)
    for x in layers[1:]:
        _role(plan, x, ROLE_RELAY)
    _role(plan, e, ROLE_TERM)
    plan["new_slots"], plan["terminals"] = layers, [e]
    return plan


def plan_split(ctx: Ctx, c: dict, cc: dict, day: int, pick: _Picker) -> dict:
    """拆分转出 C10~C12：受骗方 → 拆分端 S → N 个末端（收款方互不相同）。

    先抽总额 T，受骗方人数 = ceil(T / victim_amount 上限)；拆分合计 S = T × part_sum_ratio；
    笔数 N ∈ [max(parts 下限, ceil(S/单笔上限)), min(parts 上限, S // 单笔下限)]，无解则重抽 T。
    """
    rng, plan = ctx.rng, _new_plan(c, day)
    v_lo, v_hi = cc["victim_amount"]
    n_lo_v, n_hi_v = _count(c["victims"])
    p_lo, p_hi = c["part_amount"]
    for _ in range(MAX_TRIES):
        T = rng.randint(*c["total"])
        nv = -(-T // v_hi)
        if not (n_lo_v <= nv <= n_hi_v and nv * v_lo <= T):
            continue
        S = rng.randint(math.ceil(T * c["part_sum_ratio"][0]), math.floor(T * c["part_sum_ratio"][1]))
        n_lo, n_hi = max(c["parts"][0], -(-S // p_hi)), min(c["parts"][1], S // p_lo)
        if n_lo <= n_hi:
            break
    else:
        raise RuntimeError(f"{c['chain_id']}: 抽不到可行的总额与笔数")
    amounts = _split_sum(rng, T, nv, v_lo, v_hi)
    n = rng.randint(n_lo, n_hi)
    parts = _split_sum(rng, S, n, p_lo, p_hi)
    victims = [pick.take() for _ in range(nv)]
    s_acct = pick.take()
    recv = [pick.take() for _ in range(n)]
    last_in = _inflows(ctx, cc, plan, victims, amounts, s_acct, _start(ctx, c, cc, day))
    first = last_in + rng.randint(*c["split_delay_min"])
    spread = rng.randint(*c["split_spread_min"])
    if spread - 1 < n - 2:
        raise RuntimeError(f"{c['chain_id']}: split_spread_min 太短，放不下 {n} 笔不同分钟的转出")
    times = [first] + sorted(rng.sample(range(first + 1, first + spread), n - 2)) + [first + spread]
    for t, r, a in zip(times, recv, parts):
        plan["txs"].append(_tx(t, s_acct, r, a))
    _role(plan, s_acct, ROLE_SPLIT)
    for r in recv:
        _role(plan, r, ROLE_TERM)
    plan["new_slots"], plan["terminals"] = [s_acct], recv
    return plan


PLANNERS = {"快进快出": plan_ffio, "分层中转": plan_layered, "拆分转出": plan_split}


def plan_withdrawals(ctx: Ctx, plans: list[dict], cc: dict, cash: str) -> None:
    """从全部末端中抽 round(ratio × 末端数) 个，在到账后 withdraw_delay_min 内提现到 CASH（同一自然日）。"""
    rng = ctx.rng
    terms = [(p, a) for p in plans for a in p["terminals"]]
    k = round(cc["terminal_withdraw_ratio"] * len(terms))
    for i in sorted(rng.sample(range(len(terms)), k)):
        plan, acct = terms[i]
        inflow = [x for x in plan["txs"] if x["to"] == acct and x["tx_type"] == TX_TRANSFER]
        got, t_in = sum(x["amount"] for x in inflow), max(x["t"] for x in inflow)
        d_lo, d_hi = cc["withdraw_delay_min"]
        d_hi = min(d_hi, plan["day"] * 1440 + 1439 - t_in, ctx.t_end - t_in)
        if d_hi < d_lo:
            raise RuntimeError(f"{plan['chain_id']}: {acct} 到账太晚，当天放不下提现")
        r_lo, r_hi = cc["withdraw_amount_ratio"]
        amount = rng.randint(math.ceil(got * r_lo), math.floor(got * r_hi))
        plan["txs"].append(_tx(t_in + rng.randint(d_lo, d_hi), acct, cash, amount, TX_WITHDRAW))


def plan_new_accounts(ctx: Ctx, plans: list[dict], cc: dict) -> None:
    """一级收款端、中转端、拆分端（EMP_MULES 除外：他们是领工资的老户）中抽约一半改为新开户。"""
    rng, mules = ctx.rng, set(ctx.emp_mules)
    slots = [a for p in plans for a in p["new_slots"] if a not in mules]
    k = round(cc["intermediate_new_account_ratio"] * len(slots))
    by_id = {a["acct_id"]: a for a in ctx.accounts}
    for i in sorted(rng.sample(range(len(slots)), k)):
        days = rng.randint(*cc["new_account_open_days_before"])
        by_id[slots[i]]["open_date"] = (ctx.t0.date() - timedelta(days=days)).isoformat()


def plan_d3(ctx: Ctx, d: dict) -> dict:
    """D3 合租转发：F → P（14:00）→ L（15:30），P 另有 1 笔第二家企业的工资。F、P、L 为池外个人。"""
    if d.get("parties_from") != "non_pool_persons" or d["salary"].get("from") != "second_employer":
        raise NotImplementedError("D3 只支持 parties_from=non_pool_persons、salary.from=second_employer")
    rng = ctx.rng
    names = []
    for x in d["transfers"]:
        names += [n for n in (x["from"], x["to"]) if n not in names]
    pool = set(ctx.pool)
    persons = [p for p in ctx.by_type["个人"] if p not in pool]
    who = dict(zip(names, rng.sample(persons, len(names))))
    ctx.d3_parties = [who[n] for n in names]
    ctx.second_employer = rng.choice(ctx.by_type["企业"])
    first_t = ctx.minute(d["transfers"][0]["time"])
    plan = {"chain_id": "", "pattern": d["pattern"], "day": first_t // 1440, "txs": [], "rows": [],
            "new_slots": [], "terminals": [], "transfers_before": None, "quiet_margin": d.get("quiet_margin_min")}
    sal = ctx.prof["background"]["salary"]
    receiver = who[d["transfers"][0]["to"]]                    # 工资给转发人 P（第一笔转账的收款方）
    plan["txs"].append(_tx(ctx.minute(d["salary"]["time"]), ctx.second_employer, receiver,
                           rng.randint(*d["salary"]["amount"]), sal["tx_type"]))
    for x in d["transfers"]:
        plan["txs"].append(_tx(ctx.minute(x["time"]), who[x["from"]], who[x["to"]], x["amount"]))
    plan["rows"].append({"acct_id": ctx.second_employer, "chain_id": "", "pattern": "工资", "role": "无"})
    for a in ctx.d3_parties:
        plan["rows"].append({"acct_id": a, "chain_id": "", "pattern": d["pattern"], "role": "无"})
    return plan


def check_plan(ctx: Ctx, plan: dict, cc: dict) -> None:
    """蓝图自检：链上转账与提现在同一自然日、不越界；C03 的转账在 all_transfers_before 之前。"""
    tag = plan["chain_id"] or plan["pattern"]
    moves = [x for x in plan["txs"] if x["tx_type"] in (TX_TRANSFER, TX_WITHDRAW)]
    for x in plan["txs"]:
        if not 0 <= x["t"] <= ctx.t_end:
            raise RuntimeError(f"{tag}: 交易时间越界 {x}")
    if cc.get("same_natural_day") and any(x["t"] // 1440 != plan["day"] for x in moves):
        raise RuntimeError(f"{tag}: 链路跨越自然日")
    if plan["transfers_before"]:
        lim = plan["day"] * 1440 + hhmm(plan["transfers_before"])
        if any(x["t"] >= lim for x in moves if x["tx_type"] == TX_TRANSFER):
            raise RuntimeError(f"{tag}: 转账未在 {plan['transfers_before']} 前结束")


def reserve_plan(ctx: Ctx, plan: dict, margin: int, natural_day: bool, cash: str) -> None:
    """登记静默期（首笔前、末笔后各 margin 分钟，natural_day 时再并上整个自然日）与首次对手约束
    （fresh_counterparty：链上任意两个账户之间除蓝图交易外无任何交易）。"""
    moves = [x for x in plan["txs"] if x["tx_type"] in (TX_TRANSFER, TX_WITHDRAW)]
    lo, hi = min(x["t"] for x in moves) - margin, max(x["t"] for x in moves) + margin
    if natural_day:
        lo, hi = min(lo, plan["day"] * 1440), max(hi, plan["day"] * 1440 + 1439)
    lo, hi = max(0, lo), min(ctx.t_end, hi)
    accts = []
    for x in moves:
        accts += [a for a in (x["from"], x["to"]) if a != cash and a not in accts]
    for a in accts:
        ctx.res.add_quiet(a, lo, hi)
    for i, a in enumerate(accts):                              # 链上任意两个账户之间都不得有背景往来
        for b in accts[i + 1:]:
            ctx.res.add_no_pair(a, b)
    for x in plan["txs"]:                                      # 含 D3 的第二家企业 → P
        if x["to"] != cash:
            ctx.res.add_no_pair(x["from"], x["to"])


def plan_chains(ctx: Ctx) -> list[dict]:
    """生成 12 条链和 D3 的蓝图，改新开户日期，登记 ctx.res，返回蓝图列表（profile 顺序，D3 在最后）。"""
    prof, rng = ctx.prof, ctx.rng
    cc = prof["chain_common"]
    cash = yaml.safe_load((SPEC / "enums.yaml").read_text(encoding="utf-8"))["special_ids"]["cash"]
    if cc.get("days") != "round_robin":
        raise NotImplementedError(f"chain_common.days={cc.get('days')} 未实现")
    order = [c["chain_id"] for c in prof["chains"]]
    rng.shuffle(order)
    day_of = {cid: i % ctx.days for i, cid in enumerate(order)}

    pick = _Picker(ctx)
    plans = [PLANNERS[c["pattern"]](ctx, c, cc, day_of[c["chain_id"]], pick) for c in prof["chains"]]
    plan_withdrawals(ctx, plans, cc, cash)
    plan_new_accounts(ctx, plans, cc)
    for d in prof.get("distractors", []):
        if d["id"] == "D3":
            plans.append(plan_d3(ctx, d))

    natural_day = cc.get("quiet_scope") == "natural_day"
    for p in plans:
        check_plan(ctx, p, cc)
        reserve_plan(ctx, p, p.get("quiet_margin") or cc["quiet_margin_min"], natural_day, cash)

    if cc.get("r02_guard"):
        r02 = next(r for r in yaml.safe_load((SPEC / "rules" / "rules_v1.yaml").read_text(encoding="utf-8"))["rules"]
                   if r["rule_id"] == "R02")
        ctx.res.guard_window, ctx.res.guard_min_sources = r02["params"]["window_min"], r02["params"]["min_sources"]
        v1_detected = set(prof["expectations"]["chain_detected"]["v1"])
        for p in plans:
            if p["chain_id"] and p["chain_id"] not in v1_detected:
                for r in p["rows"]:
                    if r["role"] == ROLE_VICTIM:
                        ctx.res.add_src_guard(r["acct_id"])
        for a in ctx.d3_parties:
            ctx.res.add_src_guard(a)
    return plans


def write_plan(ctx: Ctx, plan: dict) -> None:
    """照蓝图写交易与答案行；涉诈链上账户之间的转账记入 answer_tx（提现不记）。"""
    for x in plan["txs"]:
        seq = ctx.add_tx(x["t"], x["from"], x["to"], x["amount"], x["tx_type"])
        if plan["chain_id"] and x["tx_type"] == TX_TRANSFER:
            ctx.answer_tx.append((seq, plan["chain_id"]))
    ctx.answer.extend(plan["rows"])


def order_answer(rows: list[dict]) -> list[dict]:
    """涉诈行按 (chain_id, 角色顺序, acct_id) 在前；干扰行按 工资、商户、合租转发 分组，组内保持生成顺序。"""
    fraud = sorted((r for r in rows if r["chain_id"]),
                   key=lambda r: (r["chain_id"], ROLE_ORDER.index(r["role"]), r["acct_id"]))
    benign = sorted((r for r in rows if not r["chain_id"]), key=lambda r: BENIGN_ORDER.index(r["pattern"]))
    return fraud + benign


def background_answer_rows(ctx: Ctx) -> list[dict]:
    """干扰 D1（工资企业与纯员工）、D2（全部商户）的答案行；EMP_MULES 只登记所在链，不在此处。"""
    mules = set(ctx.emp_mules)
    rows = [{"acct_id": ctx.employer, "chain_id": "", "pattern": "工资", "role": "无"}]
    rows += [{"acct_id": e, "chain_id": "", "pattern": "工资", "role": "无"} for e in ctx.employees if e not in mules]
    rows += [{"acct_id": m, "chain_id": "", "pattern": "商户", "role": "无"} for m in ctx.by_type["商户"]]
    return rows


# ---------------------------------------------------------------- 输出
def finalize(ctx: Ctx) -> tuple[list[dict], list[dict], dict[int, str]]:
    """按 (time, 生成顺序) 排序后统一编号；返回账户行、交易行、seq→tx_id 映射。"""
    width = max(5, len(str(len(ctx.txs))))
    order = sorted(ctx.txs, key=lambda x: (x["t"], x["seq"]))
    seq2id, tx_rows = {}, []
    for i, x in enumerate(order, 1):
        tx_id = f"T{i:0{width}d}"
        seq2id[x["seq"]] = tx_id
        tx_rows.append({"tx_id": tx_id, "time": ctx.fmt(x["t"]), "from_acct": x["from"], "to_acct": x["to"],
                        "amount": x["amount"], "tx_type": x["tx_type"]})
    acct_rows = sorted(ctx.accounts, key=lambda a: a["acct_id"])
    return acct_rows, tx_rows, seq2id


def write_csv(path: Path, cols: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_meta(ctx: Ctx, out: Path, n_acct: int, n_tx: int) -> dict:
    p = ctx.prof
    meta = {
        "dataset_id": p["dataset_id_format"].format(profile=p["profile"], seed=ctx.seed),
        "spec_version": p["spec_version"],
        "source": "synthetic",
        "profile": p["profile"],
        "generator": "core/gen_data.py",
        "seed": ctx.seed,
        "time_range": list(p["time_range"]),
        "timezone": p["timezone"],
        "currency": "CNY",
        "amount_unit": "元",
        "row_counts": {"accounts": n_acct, "transactions": n_tx},
        "sha256": {"accounts.csv": sha256(out / "accounts.csv"), "transactions.csv": sha256(out / "transactions.csv")},
    }
    (out / "dataset_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8", newline="\n")
    return meta


# ---------------------------------------------------------------- 摘要（自检用，不是规则的正式实现）
def r02_like_hits(tx_rows: list[dict], window: int, min_sources: int, types: set[str]) -> set[str]:
    """估算 R02：[t, t+window] 内转入来源去重数 ≥ min_sources 的账户。"""
    t0 = datetime.strptime(tx_rows[0]["time"], TIME_FMT) if tx_rows else None
    inflow = defaultdict(list)
    for r in tx_rows:
        if r["tx_type"] in types and r["to_acct"] != "CASH":
            m = int((datetime.strptime(r["time"], TIME_FMT) - t0).total_seconds() // 60)
            inflow[r["to_acct"]].append((m, r["from_acct"]))
    hits = set()
    for acct, ev in inflow.items():
        ev.sort()
        j = 0
        for i in range(len(ev)):
            while ev[i][0] - ev[j][0] > window:
                j += 1
            if len({s for _, s in ev[j:i + 1]}) >= min_sources:
                hits.add(acct)
                break
    return hits


def summarize(ctx: Ctx, acct_rows: list[dict], tx_rows: list[dict], meta: dict) -> None:
    by_type = defaultdict(int)
    for r in tx_rows:
        by_type[r["tx_type"]] += 1
    hf_day = defaultdict(int)
    hf = set(ctx.hf_merchants)
    for r in tx_rows:
        if r["to_acct"] in hf:
            hf_day[(r["to_acct"], r["time"][:10])] += 1
    nm_cnt = defaultdict(int)
    nm = set(ctx.normal_merchants)
    for r in tx_rows:
        if r["to_acct"] in nm:
            nm_cnt[r["to_acct"]] += 1
    chain_seqs = {s for s, _ in ctx.answer_tx}
    d3 = set(ctx.d3_parties)
    transfers = [x["amount"] for x in ctx.txs if x["tx_type"] == "转账" and x["seq"] not in chain_seqs
                 and not (x["from"] in d3 and x["to"] in d3)]
    acct_type = {a["acct_id"]: a["acct_type"] for a in acct_rows}

    print(f"dataset_id   {meta['dataset_id']}")
    print(f"账户         {len(acct_rows)}：" + "、".join(f"{t} {len(v)}" for t, v in ctx.by_type.items()))
    print(f"交易         {len(tx_rows)}：" + "、".join(f"{t} {n}" for t, n in sorted(by_type.items())))
    print(f"候选池       {len(ctx.pool)} 个；EMP_MULES {ctx.emp_mules}；工资企业 {ctx.employer}")
    if transfers:
        print(f"个人互转金额 {min(transfers)}~{max(transfers)}（背景，{len(transfers)} 笔）")
    if hf_day:
        print(f"高频商户     {len(hf)} 家，每天 {min(hf_day.values())}~{max(hf_day.values())} 笔")
    if nm_cnt:
        print(f"普通商户     {len(nm)} 家，每周 {min(nm_cnt.values())}~{max(nm_cnt.values())} 笔，合计 {sum(nm_cnt.values())}")
    r02 = next((r for r in yaml.safe_load((SPEC / "rules" / "rules_v1.yaml").read_text(encoding="utf-8"))["rules"]
                if r["rule_id"] == "R02"), None)
    if r02:
        hits = r02_like_hits(tx_rows, r02["params"]["window_min"], r02["params"]["min_sources"], set(r02["in_types"]))
        persons = sum(1 for a in hits if acct_type.get(a) == "个人")
        print(f"R02 估算     个人 {persons}、高频商户 {len(hits & hf)}/{len(hf)}、普通商户 {len(hits & nm)}/{len(nm)}"
              f"（窗口 {r02['params']['window_min']} 分钟，来源 ≥ {r02['params']['min_sources']}）")
    if ctx.answer:
        first_t, n_tx = {}, defaultdict(int)
        by_seq = {x["seq"]: x for x in ctx.txs}
        for s, c in ctx.answer_tx:
            first_t[c] = min(first_t.get(c, by_seq[s]["t"]), by_seq[s]["t"])
            n_tx[c] += 1
        days = defaultdict(list)
        for c in sorted(first_t):
            days[ctx.fmt(first_t[c])[5:10]].append(f"{c}({n_tx[c]})")
        t0 = ctx.t0.date().isoformat()
        fresh = sum(1 for a in acct_rows if a["open_date"] > (ctx.t0.date() - timedelta(days=30)).isoformat()
                    and a["open_date"] <= t0)
        fraud = [r for r in ctx.answer if r["chain_id"]]
        print(f"埋入链路     {len(first_t)} 条，链上转账 {len(ctx.answer_tx)} 笔，提现 {by_type.get('提现', 0)} 笔；"
              f"新开户（30 天内）{fresh} 个")
        print("按日分布     " + "  ".join(f"{d}: {' '.join(v)}" for d, v in sorted(days.items())))
        if ctx.d3_parties:
            print(f"D3           F/P/L = {'/'.join(ctx.d3_parties)}；第二家企业 {ctx.second_employer}")
        print(f"答案         answer.csv {len(ctx.answer)} 行（涉诈 {len(fraud)}、干扰 {len(ctx.answer) - len(fraud)}），"
              f"answer_tx.csv {len(ctx.answer_tx)} 行")
    print("sha256       " + "  ".join(f"{k} {v[:12]}…" for k, v in meta["sha256"].items()))


# ---------------------------------------------------------------- 主流程
def build(prof: dict, seed: int, stage: str) -> Ctx:
    ctx = new_ctx(prof, seed)
    gen_accounts(ctx)
    pick_pool(ctx)
    if stage == "full":
        plans = plan_chains(ctx)                 # 先抽蓝图并登记约束，背景才能避开
        gen_background(ctx)
        for plan in plans:
            write_plan(ctx, plan)
        ctx.answer = order_answer(background_answer_rows(ctx) + ctx.answer)
    else:
        gen_background(ctx)
    return ctx


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="按 gen_profile 生成仿真交易数据")
    ap.add_argument("--profile", type=Path, default=DEFAULT_PROFILE, help="生成配置（默认 Data and Rules/gen_profile_v1.yaml）")
    ap.add_argument("--seed", type=int, help="随机种子（默认取 profile.seed）")
    ap.add_argument("--stage", choices=["background", "full"], default="full",
                    help="background=只有背景数据；full=背景 + 12 条链 + D3，并写答案")
    ap.add_argument("--out", type=Path, default=ROOT / "data", help="数据输出目录（默认 data/）")
    ap.add_argument("--eval-out", type=Path, default=ROOT / "eval", help="答案输出目录（仅 full 阶段）")
    ap.add_argument("--force", action="store_true", help="输出目录已有 dataset_meta.json 时允许覆盖（数据冻结后慎用）")
    ap.add_argument("--quiet", action="store_true", help="不打印摘要")
    a = ap.parse_args(argv)

    prof = load_profile(a.profile)
    seed = prof["seed"] if a.seed is None else a.seed
    if (a.out / "dataset_meta.json").exists() and not a.force:
        print(f"{a.out} 已有数据集，未覆盖。数据冻结后不要重新生成；确需覆盖请加 --force。", file=sys.stderr)
        return 2

    try:
        ctx = build(prof, seed, a.stage)
    except NotImplementedError as e:
        print(f"未实现：{e}", file=sys.stderr)
        return 3

    acct_rows, tx_rows, seq2id = finalize(ctx)
    a.out.mkdir(parents=True, exist_ok=True)
    write_csv(a.out / "accounts.csv", ACCT_COLS, acct_rows)
    write_csv(a.out / "transactions.csv", TX_COLS, tx_rows)
    meta = write_meta(ctx, a.out, len(acct_rows), len(tx_rows))
    if a.stage == "full":
        write_csv(a.eval_out / "answer.csv", ["acct_id", "chain_id", "pattern", "role"], ctx.answer)
        write_csv(a.eval_out / "answer_tx.csv", ["tx_id", "chain_id"],
                  [{"tx_id": seq2id[s], "chain_id": c} for s, c in sorted(ctx.answer_tx, key=lambda x: seq2id[x[0]])])

    if not a.quiet:
        summarize(ctx, acct_rows, tx_rows, meta)
        if a.stage == "background":
            print("注意：background 阶段只有背景数据，不含诈骗链，也不写答案。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
