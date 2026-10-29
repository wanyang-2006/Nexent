"""按 Data and Rules/gen_profile_v1.yaml 生成仿真交易数据（core/gen_data.py）。

阶段：
  background（第 1 天，已实现）：账户、涉案候选池、个人互转、消费、工资。只写 data/。
  full      （第 2 天，待实现）：先登记埋链约束，再生成背景，然后埋入 12 条链与干扰，
                                  并写 eval/answer.csv、eval/answer_tx.csv。

用法（仓库根目录）：
  python -m core.gen_data --seed 42                 # 生成到 data/
  python -m core.gen_data --seed 42 --force         # data/ 已有数据时覆盖
  python -m core.gen_data --seed 42 --out tmp_a     # 输出到其他目录（自测哈希一致性用）
  python "Data and Rules/validate_spec.py" --skip-spec --data data

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
import random
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
    """埋链前登记的约束，背景交易生成时必须避开（第 1 天为空）。

    quiet:   账户 -> 若干闭区间 [lo, hi]（距数据起点的分钟数），区间内该账户不得有背景“转账”
             （对应 chain_common.quiet_margin_min）
    no_pair: 不得有任何背景交易往来的账户对（对应 chain_common.fresh_counterparty）
    """
    quiet: dict[str, list[tuple[int, int]]] = field(default_factory=dict)
    no_pair: set[frozenset[str]] = field(default_factory=set)

    def add_quiet(self, acct: str, lo: int, hi: int) -> None:
        self.quiet.setdefault(acct, []).append((lo, hi))

    def add_no_pair(self, a: str, b: str) -> None:
        self.no_pair.add(frozenset((a, b)))

    def blocks_transfer(self, a: str, b: str, t: int) -> bool:
        if frozenset((a, b)) in self.no_pair:
            return True
        return any(lo <= t <= hi for x in (a, b) for lo, hi in self.quiet.get(x, ()))

    def blocks_pair(self, a: str, b: str) -> bool:
        return frozenset((a, b)) in self.no_pair


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
    hf_merchants: list[str] = field(default_factory=list)
    normal_merchants: list[str] = field(default_factory=list)
    txs: list[dict] = field(default_factory=list)               # t(分钟), from, to, amount, tx_type, seq
    res: Reservations = field(default_factory=Reservations)
    answer: list[dict] = field(default_factory=list)            # 第 2 天：acct_id, chain_id, pattern, role
    answer_tx: list[tuple[int, str]] = field(default_factory=list)  # 第 2 天：(交易 seq, chain_id)

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
    cfg, rng = ctx.prof["background"]["salary"], ctx.rng
    if cfg["employer_count"] != 1:
        raise NotImplementedError("v1 只支持 1 家工资企业")
    ctx.employer = rng.choice(ctx.by_type["企业"])
    pool_set = set(ctx.pool)
    others = [p for p in ctx.by_type["个人"] if p not in pool_set]
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


# ---------------------------------------------------------------- 第 2 天：埋链与干扰（待实现）
# 顺序：gen_accounts → pick_pool → plan_chains（登记 Reservations、改新开户日期）→ gen_background
#       → inject_* → finalize。plan_chains 必须在 gen_background 之前调用，背景交易才能避开静默期与链上账户对。
# ctx.emp_mules 已在 pick_pool 中确定：[0] 用作 C04 一级收款端，[1] 用作 C08 的 L2；其余角色从 pool 中不放回抽取。
# 不要只在背景生成后再挑“恰好静默”的账户：每人每天约 1.6 笔互转，一条 11 个账户的拆分链几乎找不到满足条件的组合。
def plan_chains(ctx: Ctx) -> list[dict]:
    """为 12 条链和 D3 分配日期、起始时间、候选池账户，登记 ctx.res，返回链计划。"""
    raise NotImplementedError("第 2 天实现：plan_chains")


def inject_ffio(ctx: Ctx, plan: dict) -> None:
    """快进快出 C01~C06。"""
    raise NotImplementedError("第 2 天实现：inject_ffio")


def inject_layered(ctx: Ctx, plan: dict) -> None:
    """分层中转 C07~C09。"""
    raise NotImplementedError("第 2 天实现：inject_layered")


def inject_split(ctx: Ctx, plan: dict) -> None:
    """拆分转出 C10~C12。抽样见甲文档 6.2：按拆分合计 S 计算笔数范围。"""
    raise NotImplementedError("第 2 天实现：inject_split")


def inject_d3(ctx: Ctx, plan: dict) -> None:
    """可选干扰 D3 合租转发（含第二家企业的工资）。"""
    raise NotImplementedError("第 2 天实现：inject_d3")


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
    transfers = [r["amount"] for r in tx_rows if r["tx_type"] == "转账"]
    acct_type = {a["acct_id"]: a["acct_type"] for a in acct_rows}

    print(f"dataset_id   {meta['dataset_id']}")
    print(f"账户         {len(acct_rows)}：" + "、".join(f"{t} {len(v)}" for t, v in ctx.by_type.items()))
    print(f"交易         {len(tx_rows)}：" + "、".join(f"{t} {n}" for t, n in sorted(by_type.items())))
    print(f"候选池       {len(ctx.pool)} 个；EMP_MULES {ctx.emp_mules}；工资企业 {ctx.employer}")
    if transfers:
        print(f"个人互转金额 {min(transfers)}~{max(transfers)}")
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
    print("sha256       " + "  ".join(f"{k} {v[:12]}…" for k, v in meta["sha256"].items()))


# ---------------------------------------------------------------- 主流程
def build(prof: dict, seed: int, stage: str) -> Ctx:
    ctx = new_ctx(prof, seed)
    gen_accounts(ctx)
    pick_pool(ctx)
    if stage == "full":
        plans = plan_chains(ctx)                 # 第 2 天：先登记约束
        gen_background(ctx)
        for plan in plans:
            {"快进快出": inject_ffio, "分层中转": inject_layered, "拆分转出": inject_split,
             "合租转发": inject_d3}[plan["pattern"]](ctx, plan)
        ctx.answer = background_answer_rows(ctx) + ctx.answer
    else:
        gen_background(ctx)
    return ctx


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="按 gen_profile 生成仿真交易数据")
    ap.add_argument("--profile", type=Path, default=DEFAULT_PROFILE, help="生成配置（默认 Data and Rules/gen_profile_v1.yaml）")
    ap.add_argument("--seed", type=int, help="随机种子（默认取 profile.seed）")
    ap.add_argument("--stage", choices=["background", "full"], default="background",
                    help="background=第 1 天背景数据；full=第 2 天含埋链与答案（待实现）")
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
            print("注意：当前只有背景数据（第 1 天），不含诈骗链；第 2 天用 --stage full --force 重新生成后再冻结。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
