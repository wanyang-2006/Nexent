#!/usr/bin/env python3
"""数据与规则规范校验脚本（Data and Rules/validate_spec.py）

用法（在仓库根目录运行）：
  python "Data and Rules/validate_spec.py"                                 # 校验规范自身 + examples
  python "Data and Rules/validate_spec.py" --data data --eval eval         # 校验生成的数据集
  python "Data and Rules/validate_spec.py" --fixtures core/fixtures --data "Data and Rules/examples/data"
  python "Data and Rules/validate_spec.py" --tickets tickets/v1 --data data
  python "Data and Rules/validate_spec.py" --check-leak core mcp_server    # 工具代码不得引用 eval/

依赖：pyyaml、jsonschema（>=4.18）。退出码：0 通过，1 有错误。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

SPEC = Path(__file__).resolve().parent
TIME_FMT = "%Y-%m-%d %H:%M"
FIXTURE_SCHEMAS = {
    "get_account": "get_account", "get_transactions": "get_transactions", "trace_chain": "trace_chain",
    "check_rules": "check_rules", "make_ticket": "make_ticket", "rejudge": "rejudge", "error": "error",
}


# ---------------------------------------------------------------- 输出
class Report:
    def __init__(self):
        self.errors, self.warnings, self.section = [], [], ""

    def start(self, name):
        self.section = name
        print(f"\n== {name}")

    def err(self, msg):
        self.errors.append(f"[{self.section}] {msg}")
        print(f"  ERROR  {msg}")

    def warn(self, msg):
        self.warnings.append(f"[{self.section}] {msg}")
        print(f"  WARN   {msg}")

    def ok(self, msg):
        print(f"  ok     {msg}")


R = Report()


# ---------------------------------------------------------------- 加载
def load_yaml(p: Path):
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def load_spec():
    enums = load_yaml(SPEC / "enums.yaml")
    schema = load_yaml(SPEC / "data_schema_v1.yaml")
    profile = load_yaml(SPEC / "gen_profile_v1.yaml")
    rules = {}
    for p in sorted((SPEC / "rules").glob("rules_v*.yaml")):
        rules[p.stem.split("_", 1)[1]] = (p, load_yaml(p))
    schemas = {p.name.replace(".schema.json", ""): load_json(p) for p in sorted((SPEC / "schemas").glob("*.schema.json"))}
    registry = Registry().with_resources([(s["$id"], Resource.from_contents(s)) for s in schemas.values()])
    return enums, schema, profile, rules, schemas, registry


def active(enums, name, key="value"):
    return [e[key] for e in enums["enums"][name] if e.get("state", "active") == "active"]


def to_min(t: str) -> int:
    return int(datetime.strptime(t, TIME_FMT).timestamp() // 60)


def schema_errors(schemas, registry, name, obj):
    v = Draft202012Validator(schemas[name], registry=registry)
    return [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}" for e in v.iter_errors(obj)]


# ---------------------------------------------------------------- 1 枚举
def check_enums(enums, schemas):
    R.start("enums.yaml")
    for name, items in enums["enums"].items():
        for key in ("value", "code"):
            vals = [i[key] for i in items if key in i]
            if len(vals) != len(set(vals)):
                R.err(f"{name}.{key} 有重复")
        for i in items:
            if i.get("state", "active") not in ("active", "reserved", "deprecated"):
                R.err(f"{name}: 非法 state {i.get('state')}")
    sev = [s["severity"] for s in enums["enums"]["status"]]
    if sorted(sev) != list(range(len(sev))):
        R.err("status.severity 必须为 0..n-1 且不重复")
    acts = set(active(enums, "action"))
    for s in enums["enums"]["status"]:
        if s["action"] is not None and s["action"] not in acts:
            R.err(f"status {s['value']} 的 action 不在 action 枚举中")
    # schema 中的枚举必须与 enums.yaml 的 active 值一致
    common = schemas["common"]["$defs"]
    pairs = {"acct_type": ("acct_type", "value"), "tx_type": ("tx_type", "value"), "status": ("status", "value"),
             "status_code": ("status", "code"), "role": ("role", "value"), "action": ("action", "value"),
             "rule_type": ("rule_type", "value"), "rule_level": ("rule_level", "value"),
             "gap_code": ("gap_code", "code"), "error_code": ("error_code", "code"), "direction": ("direction", "value")}
    for d, (en, key) in pairs.items():
        if set(common[d]["enum"]) != set(active(enums, en, key)):
            R.err(f"schemas/common.$defs.{d} 与 enums.{en}.{key}（active）不一致")
    for k, pat in enums["id_patterns"].items():
        re.compile(pat)
    R.ok(f"{len(enums['enums'])} 组枚举，{len(enums['rule_impls'])} 个规则实现")


# ---------------------------------------------------------------- 2 规则
def resolve_window(ruleset):
    rid, param = ruleset["trace"]["window_from"].split(".")
    for r in ruleset["rules"]:
        if r["rule_id"] == rid:
            return r["params"][param]
    raise KeyError(ruleset["trace"]["window_from"])


def rule_by_id(ruleset, rid):
    return next((r for r in ruleset["rules"] if r["rule_id"] == rid), None)


def check_rules(enums, rules, schemas, registry):
    R.start("rules/*.yaml")
    impls = enums["rule_impls"]
    seen_identity = {}
    for ver, (path, rs) in sorted(rules.items(), key=lambda kv: int(kv[0][1:])):
        for e in schema_errors(schemas, registry, "rules", rs):
            R.err(f"{path.name}: {e}")
        if rs.get("version") != ver:
            R.err(f"{path.name}: version 字段 {rs.get('version')} 与文件名不一致")
        if rs.get("based_on") and rs["based_on"] not in rules:
            R.err(f"{path.name}: based_on {rs['based_on']} 不存在")
        ids = [r["rule_id"] for r in rs.get("rules", [])]
        if len(ids) != len(set(ids)):
            R.err(f"{path.name}: rule_id 重复")
        for r in rs.get("rules", []):
            rid = r["rule_id"]
            impl = impls.get(r.get("impl"))
            if impl is None:
                R.err(f"{path.name} {rid}: impl {r.get('impl')} 未在 enums.rule_impls 登记")
                continue
            if set(r["params"]) != set(impl["params"]):
                R.err(f"{path.name} {rid}: params {sorted(r['params'])} 应为 {sorted(impl['params'])}")
            for t in impl["types"]:
                if not r.get(t):
                    R.err(f"{path.name} {rid}: impl {r['impl']} 需要 {t}")
            for t in ("in_types", "out_types"):
                if r.get(t) and t not in impl["types"]:
                    R.warn(f"{path.name} {rid}: {t} 对 impl {r['impl']} 无作用")
            if f"{ver}#{rid}" not in r["aligned_to"] and "仿真内部规则" in r["aligned_to"]:
                R.warn(f"{path.name} {rid}: aligned_to 建议写成 仿真内部规则{ver}#{rid}")
            ident = (r["name"], r["type"], r["impl"])
            if rid in seen_identity and seen_identity[rid][1] != ident:
                R.err(f"{rid}: 在 {seen_identity[rid][0]} 与 {ver} 中 name/type/impl 不同（规则号不得复用）")
            seen_identity.setdefault(rid, (ver, ident))
        try:
            w = resolve_window(rs)
            R.ok(f"{path.name}: {len(ids)} 条规则，追链窗口 W={w}")
        except KeyError as e:
            R.err(f"{path.name}: trace.window_from 指向不存在的参数 {e}")


def rules_diff(old, new):
    """返回 02 规范 6.2 节格式的差异。"""
    o = {r["rule_id"]: r for r in old["rules"]}
    n = {r["rule_id"]: r for r in new["rules"]}
    changed = []
    for rid in sorted(set(o) & set(n)):
        for k in ("level", "in_types", "out_types", "state"):
            if o[rid].get(k) != n[rid].get(k):
                changed.append({"rule_id": rid, "field": k, "old": o[rid].get(k), "new": n[rid].get(k)})
        for k in sorted(set(o[rid]["params"]) | set(n[rid]["params"])):
            if o[rid]["params"].get(k) != n[rid]["params"].get(k):
                changed.append({"rule_id": rid, "field": f"params.{k}", "old": o[rid]["params"].get(k), "new": n[rid]["params"].get(k)})
    trace_changed = []
    wo, wn = resolve_window(old), resolve_window(new)
    if wo != wn:
        trace_changed.append({"field": "W", "old": wo, "new": wn, "reason": f"window_from={new['trace']['window_from']}"})
    for k in sorted(set(old["trace"]) | set(new["trace"])):
        if old["trace"].get(k) != new["trace"].get(k):
            trace_changed.append({"field": k, "old": old["trace"].get(k), "new": new["trace"].get(k)})
    return {"from": old["version"], "to": new["version"],
            "added": [{"rule_id": r, "name": n[r]["name"]} for r in sorted(set(n) - set(o))],
            "removed": [{"rule_id": r, "name": o[r]["name"]} for r in sorted(set(o) - set(n))],
            "changed": changed, "trace_changed": trace_changed}


# ---------------------------------------------------------------- 3 生成配置的时间与金额推理
def check_profile(profile, rules):
    R.start("gen_profile_v1.yaml")
    v1, v2 = rules["v1"][1], rules["v2"][1]
    w1, w2 = resolve_window(v1), resolve_window(v2)
    cc = profile["chain_common"]
    spread = cc["inflow_spread_max_min"]
    r01, r04 = rule_by_id(v2, "R01")["params"], rule_by_id(v1, "R04")["params"]
    r06, r08 = rule_by_id(v1, "R06")["params"], rule_by_id(v1, "R08")["params"]
    r03 = rule_by_id(v1, "R03")["params"]
    lo_v, hi_v = cc["victim_amount"]
    if lo_v <= r08["amount"]:
        R.err(f"victim_amount 下限 {lo_v} 必须 > R08.amount {r08['amount']}")
    if lo_v <= r06["amount"]:
        R.err(f"victim_amount 下限 {lo_v} 必须 > R06.amount {r06['amount']}（C03 夜间）")
    expect_v1 = set(profile["expectations"]["chain_detected"]["v1"])
    for c in profile["chains"]:
        cid, pat = c["chain_id"], c["pattern"]
        if pat == "快进快出":
            lo, hi = c["dwell_min"][0], spread + c["dwell_min"][1]
            if c["out_ratio"][0] < r04["ratio_min"]:
                R.err(f"{cid}: out_ratio 下限 {c['out_ratio'][0]} < R04.ratio_min {r04['ratio_min']}")
        elif pat == "分层中转":
            lo = c["first_hop_delay_min"][0]
            hi = max(spread + c["first_hop_delay_min"][1], c["hop_gap_min"][1])
            if 1 - c["hop_decay"][1] < r04["ratio_min"]:
                R.err(f"{cid}: 每跳衰减上限使比例低于 R04.ratio_min")
        elif pat == "拆分转出":
            lo = c["split_delay_min"][0]
            hi = spread + c["split_delay_min"][1] + c["split_spread_min"][1]
            if c["part_amount"][1] > r03["max_single"]:
                R.err(f"{cid}: part_amount 上限 {c['part_amount'][1]} > R03.max_single")
            if c["parts"][0] < r03["min_receivers"]:
                R.err(f"{cid}: parts 下限 < R03.min_receivers")
            feasible = [T for T in range(c["total"][0], c["total"][1] + 1, 1000)
                        if max(c["parts"][0], -(-T // c["part_amount"][1])) <= min(c["parts"][1], T // c["part_amount"][0])]
            if not feasible:
                R.err(f"{cid}: 总额与笔数、单笔区间无可行解")
        else:
            R.err(f"{cid}: 未知 pattern {pat}")
            continue
        if cid in expect_v1 and hi > w1:
            R.err(f"{cid}: 首笔转入到转出最长 {hi} 分钟，超过 v1 窗口 {w1}")
        if cid not in expect_v1 and not (lo > w1 and hi <= w2):
            R.err(f"{cid}: v2 演示链要求时间差在 ({w1}, {w2}]，实际 [{lo}, {hi}]")
    for d in profile["distractors"]:
        if d["id"] == "D3":
            a, b = d["transfers"]
            gap = to_min(b["time"]) - to_min(a["time"])
            ratio = b["amount"] / a["amount"]
            if not (w1 < gap <= w2):
                R.err(f"D3: 间隔 {gap} 分钟应在 ({w1}, {w2}]")
            if not (r01["ratio_min"] <= ratio < r04["ratio_min"]):
                R.err(f"D3: 比例 {ratio:.3f} 应满足 R01.ratio_min ≤ r < R04.ratio_min")
    R.ok(f"窗口 v1={w1}、v2={w2}；12 条链的时间与金额参数和规则阈值相容")


# ---------------------------------------------------------------- 4 数据集
def read_csv(path: Path):
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        R.err(f"{path.name}: 含 BOM")
        raw = raw[3:]
    if b"\r\n" in raw:
        R.err(f"{path.name}: 换行应为 LF")
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"), newline="")))
    header = next(csv.reader(io.StringIO(raw.decode("utf-8"))), [])
    return header, rows


def check_columns(fname, header, spec):
    req = [c["name"] for c in spec["columns"]]
    opt = [c["name"] for c in spec.get("optional_columns", [])]
    if header[:len(req)] != req:
        R.err(f"{fname}: 必需列应为 {req} 且在最前，实际 {header}")
    for h in header:
        if h in spec.get("forbidden_columns", []):
            R.err(f"{fname}: 出现禁止的标签列 {h}")
        elif h not in req and h not in opt:
            R.warn(f"{fname}: 未登记的列 {h}（请先在 data_schema 中登记为可选列）")


def sha256(p: Path):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check_dataset(data_dir: Path, eval_dir: Path | None, enums, dschema, schemas, registry, meta_required=True):
    R.start(f"数据集 {data_dir}")
    ids = enums["id_patterns"]
    files = dschema["files"]
    cash = enums["special_ids"]["cash"]
    acct_types, tx_types = set(active(enums, "acct_type")), set(active(enums, "tx_type"))

    h, accounts = read_csv(data_dir / "accounts.csv")
    check_columns("accounts.csv", h, files["accounts"])
    acct = {}
    for i, a in enumerate(accounts, 2):
        if not re.match(ids["acct_id"], a["acct_id"]):
            R.err(f"accounts.csv 行{i}: acct_id 格式错误 {a['acct_id']}")
        if a["acct_id"] in acct:
            R.err(f"accounts.csv 行{i}: acct_id 重复 {a['acct_id']}")
        if a["acct_type"] not in acct_types:
            R.err(f"accounts.csv 行{i}: acct_type 非法 {a['acct_type']}")
        if not a["name"]:
            R.err(f"accounts.csv 行{i}: name 为空")
        try:
            date.fromisoformat(a["open_date"])
        except ValueError:
            R.err(f"accounts.csv 行{i}: open_date 格式错误 {a['open_date']}")
        acct[a["acct_id"]] = a

    meta = None
    mp = data_dir / "dataset_meta.json"
    if mp.exists():
        meta = load_json(mp)
        for e in schema_errors(schemas, registry, "dataset_meta", meta):
            R.err(f"dataset_meta.json: {e}")
    elif meta_required:
        R.err("缺少 dataset_meta.json")
    t_lo, t_hi = (meta or {}).get("time_range") or dschema["time"]["dataset_range"]

    h, txs = read_csv(data_dir / "transactions.csv")
    check_columns("transactions.csv", h, files["transactions"])
    parties = dschema["tx_type_parties"]
    seen, prev = set(), None
    for i, t in enumerate(txs, 2):
        tag = f"transactions.csv 行{i} {t['tx_id']}"
        if not re.match(ids["tx_id"], t["tx_id"]):
            R.err(f"{tag}: tx_id 格式错误")
        if t["tx_id"] in seen:
            R.err(f"{tag}: tx_id 重复")
        seen.add(t["tx_id"])
        try:
            datetime.strptime(t["time"], TIME_FMT)
        except ValueError:
            R.err(f"{tag}: time 格式错误 {t['time']}")
            continue
        if not (t_lo <= t["time"] <= t_hi):
            R.err(f"{tag}: time 超出范围 {t['time']}")
        key = (t["time"], int(t["tx_id"][1:]))
        if prev and key < prev:
            R.err(f"{tag}: 未按 (time, tx_id) 升序，或 tx_id 与时间顺序不一致")
        prev = key
        try:
            amt = float(t["amount"])
            if amt <= 0 or round(amt, 2) != amt:
                raise ValueError
        except ValueError:
            R.err(f"{tag}: amount 非法 {t['amount']}")
        if t["tx_type"] not in tx_types:
            R.err(f"{tag}: tx_type 非法 {t['tx_type']}")
            continue
        f, to = t["from_acct"], t["to_acct"]
        if f == to:
            R.err(f"{tag}: 自转")
        if f not in acct:
            R.err(f"{tag}: from_acct {f} 不存在")
            continue
        rule = parties[t["tx_type"]]
        if to == cash:
            if "cash" not in rule["to"]:
                R.err(f"{tag}: 只有提现的 to_acct 可以是 CASH")
        elif to not in acct:
            R.err(f"{tag}: to_acct {to} 不存在")
            continue
        elif acct[to]["acct_type"] not in rule["to"]:
            R.err(f"{tag}: {t['tx_type']} 的收款方类型不能是 {acct[to]['acct_type']}")
        if acct[f]["acct_type"] not in rule["from"]:
            R.err(f"{tag}: {t['tx_type']} 的付款方类型不能是 {acct[f]['acct_type']}")
        d = t["time"][:10]
        for a in (f, to):
            if a in acct and d < acct[a]["open_date"]:
                R.err(f"{tag}: 交易日期早于 {a} 的开户日期")

    if meta:
        if meta["row_counts"] != {"accounts": len(accounts), "transactions": len(txs)} and \
                (meta["row_counts"]["accounts"], meta["row_counts"]["transactions"]) != (len(accounts), len(txs)):
            R.err(f"dataset_meta.row_counts 与实际行数不符（{len(accounts)}, {len(txs)}）")
        for fn, hv in meta["sha256"].items():
            p = data_dir / fn
            if p.exists() and sha256(p) != hv:
                R.err(f"dataset_meta.sha256[{fn}] 与文件不符，实际 {sha256(p)}")
    R.ok(f"accounts {len(accounts)} 行，transactions {len(txs)} 行")

    if eval_dir:
        check_answer(eval_dir, acct, {t["tx_id"] for t in txs}, enums, files)
    return acct, txs, meta


def check_answer(eval_dir, acct, tx_ids, enums, files):
    R.start(f"答案 {eval_dir}")
    pat = {p["value"]: p for p in enums["enums"]["pattern"] if p["state"] == "active"}
    roles = {r["value"] for r in enums["enums"]["role"] if r["state"] == "active" and r["in_answer"]}
    h, rows = read_csv(eval_dir / "answer.csv")
    check_columns("answer.csv", h, files["answer"])
    keys, chain_pat = set(), {}
    for i, r in enumerate(rows, 2):
        tag = f"answer.csv 行{i} {r['acct_id']}"
        if r["acct_id"] not in acct:
            R.err(f"{tag}: 账户不存在")
        if (r["acct_id"], r["chain_id"]) in keys:
            R.err(f"{tag}: (acct_id, chain_id) 重复")
        keys.add((r["acct_id"], r["chain_id"]))
        if r["pattern"] not in pat:
            R.err(f"{tag}: pattern 非法 {r['pattern']}")
            continue
        if r["role"] not in roles:
            R.err(f"{tag}: role 非法 {r['role']}")
        if pat[r["pattern"]]["kind"] == "fraud":
            if not re.match(enums["id_patterns"]["answer_chain_id"], r["chain_id"] or ""):
                R.err(f"{tag}: 涉诈行 chain_id 必填且形如 C01")
            if r["role"] == "无":
                R.err(f"{tag}: 涉诈行 role 不能为 无")
            if chain_pat.setdefault(r["chain_id"], r["pattern"]) != r["pattern"]:
                R.err(f"{tag}: 同一 chain_id 的 pattern 不一致")
        else:
            if r["chain_id"] or r["role"] != "无":
                R.err(f"{tag}: 干扰行 chain_id 应为空且 role=无")
    R.ok(f"answer.csv {len(rows)} 行，链 {len(chain_pat)} 条")
    p = eval_dir / "answer_tx.csv"
    if p.exists():
        h, rows = read_csv(p)
        check_columns("answer_tx.csv", h, files["answer_tx"])
        for i, r in enumerate(rows, 2):
            if r["tx_id"] not in tx_ids:
                R.err(f"answer_tx.csv 行{i}: 交易 {r['tx_id']} 不存在")
            if r["chain_id"] not in chain_pat:
                R.err(f"answer_tx.csv 行{i}: chain_id {r['chain_id']} 不在 answer.csv 中")
        R.ok(f"answer_tx.csv {len(rows)} 行")


# ---------------------------------------------------------------- 5 追链参考实现（02 规范 5.2 节）
def reference_chains(acct, txs, ruleset):
    tr = ruleset["trace"]
    W, cr = resolve_window(ruleset), tr["conserve_ratio"]
    E = [dict(t, t=to_min(t["time"]), amount=float(t["amount"])) for t in txs
         if t["tx_type"] in tr["edge_types"] and t["from_acct"] in acct and t["to_acct"] in acct
         and float(t["amount"]) >= tr["seed_min_amount"]]
    by_id = {e["tx_id"]: e for e in E}
    out_by, in_by = defaultdict(list), defaultdict(list)
    for e in E:
        out_by[e["from_acct"]].append(e)
        in_by[e["to_acct"]].append(e)

    def out_sum(v, lo, hi):
        return sum(x["amount"] for x in out_by[v] if lo < x["t"] <= hi)

    def in_sum(v, lo, hi):
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
    parent = {}

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
    for x in parent:
        comps[find(x)].append(x)
    chains = []
    r03 = rule_by_id(ruleset, "R03")
    min_recv = r03["params"]["min_receivers"] if r03 else 4
    for members in comps.values():
        es = sorted((by_id[x] for x in members), key=lambda e: (e["t"], e["tx_id"]))
        if max(e["amount"] for e in es) < tr["min_chain_amount"]:
            continue
        memo = {}

        def longest(x):
            if x not in memo:
                memo[x] = 1 + max((longest(y) for y in succ[x]), default=0)
            return memo[x]

        sources = [e for e in es if not pred[e["tx_id"]]]
        indeg, outdeg, recv, preds = defaultdict(int), defaultdict(int), defaultdict(set), defaultdict(set)
        for e in es:
            outdeg[e["from_acct"]] += 1
            indeg[e["to_acct"]] += 1
            recv[e["from_acct"]].add(e["to_acct"])
            preds[e["to_acct"]].add(e["from_acct"])
        accts = {e["from_acct"] for e in es} | {e["to_acct"] for e in es}
        roles = {}
        for a in accts:
            if indeg[a] == 0:
                roles[a] = "疑似受骗付款端"
        for a in accts:
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
        depth, frontier = {a: 0 for a in accts if indeg[a] == 0}, [a for a in accts if indeg[a] == 0]
        while frontier:
            nxt = []
            for a in frontier:
                for b in recv[a]:
                    if b not in depth:
                        depth[b] = depth[a] + 1
                        nxt.append(b)
            frontier = nxt
        chains.append({
            "chain_id": "L-" + min(e["tx_id"] for e in es),
            "hops": max(longest(e["tx_id"]) for e in es),
            "total_amount": sum(e["amount"] for e in sources),
            "duration_minutes": es[-1]["t"] - es[0]["t"],
            "accounts": sorted(accts, key=lambda a: (depth.get(a, 99), a)),
            "tx_ids": sorted(e["tx_id"] for e in es),
            "roles": roles,
        })
    return sorted(chains, key=lambda c: (-c["total_amount"], c["chain_id"]))


# ---------------------------------------------------------------- 6 fixtures / 工单
def collect_ids(obj, out_tx, out_acct):
    if isinstance(obj, dict):
        for k, v in obj.items():
            collect_ids(k, out_tx, out_acct)
            collect_ids(v, out_tx, out_acct)
    elif isinstance(obj, list):
        for v in obj:
            collect_ids(v, out_tx, out_acct)
    elif isinstance(obj, str):
        out_tx.update(re.findall(r"\bT\d{5,}\b", obj))
        out_acct.update(re.findall(r"\bA\d{4,}\b", obj))


def check_ticket(tk, enums, rules, tag):
    status = {s["value"]: s for s in enums["enums"]["status"]}
    s = status.get(tk.get("status"))
    if s and tk.get("status_code") and tk["status_code"] != s["code"]:
        R.err(f"{tag}: status_code 与 status 不符")
    for w in enums["conclusion_banned_words"]:
        if w in tk.get("conclusion", ""):
            R.err(f"{tag}: conclusion 含禁用词“{w}”")
    if tk.get("chain_id") and tk["chain_id"] not in tk.get("conclusion", ""):
        R.err(f"{tag}: 在链上时 conclusion 必须包含 chain_id")
    codes = [m["code"] for m in tk.get("missing_evidence", [])]
    if not codes or codes[0] != "GAP_KYC":
        R.err(f"{tag}: missing_evidence 第一项必须是 GAP_KYC")
    if tk.get("ticket_id") != f"TK-{tk.get('rule_version')}-{tk.get('acct_id')}":
        R.err(f"{tag}: ticket_id 应为 TK-<版本>-<账户>")
    rs = rules.get(tk.get("rule_version"), (None, None))[1]
    if rs:
        for b in tk.get("rule_basis", []):
            r = rule_by_id(rs, b["rule_id"])
            if not r:
                R.err(f"{tag}: rule_basis 中 {b['rule_id']} 不在 {tk['rule_version']}")
            elif (b["rule_name"], b["aligned_to"]) != (r["name"], r["aligned_to"]):
                R.err(f"{tag}: rule_basis {b['rule_id']} 的名称或 aligned_to 与规则文件不一致")
        ids = [b["rule_id"] for b in tk.get("rule_basis", [])]
        if ids != sorted(ids):
            R.err(f"{tag}: rule_basis 应按 rule_id 升序")


def check_fixtures(fx_dir: Path, enums, rules, schemas, registry, acct=None, txs=None):
    R.start(f"fixtures {fx_dir}")
    tx_by = {t["tx_id"]: t for t in (txs or [])}
    sev = {s["value"]: s["severity"] for s in enums["enums"]["status"]}
    for name, sch in FIXTURE_SCHEMAS.items():
        p = fx_dir / f"{name}.json"
        if not p.exists():
            if name != "error":
                R.err(f"缺少 {p.name}")
            continue
        n_err = len(R.errors)
        obj = load_json(p)
        errs = schema_errors(schemas, registry, sch, obj)
        for e in errs:
            R.err(f"{p.name}: {e}")
        try:
            check_fixture_semantics(p, name, obj, enums, rules, acct, txs, tx_by, sev)
        except (KeyError, TypeError, IndexError) as e:
            if not errs:
                R.err(f"{p.name}: 结构异常 {type(e).__name__}: {e}")
        if len(R.errors) == n_err:
            R.ok(p.name)


def check_fixture_semantics(p, name, obj, enums, rules, acct, txs, tx_by, sev):
    if acct is not None and name != "error":
        t_ids, a_ids = set(), set()
        collect_ids(obj, t_ids, a_ids)
        for x in sorted(t_ids - set(tx_by)):
            R.err(f"{p.name}: 交易 {x} 不存在于数据中")
        for x in sorted(a_ids - set(acct)):
            R.err(f"{p.name}: 账户 {x} 不存在于数据中")
    if name == "check_rules":
        rs = rules.get(obj.get("rule_version", "v1"))[1]
        for grp, typ in (("hits", "risk"), ("counter", "counter")):
            ids = [h["rule_id"] for h in obj[grp]]
            if ids != sorted(ids):
                R.err(f"{p.name}: {grp} 应按 rule_id 升序")
            for h in obj[grp]:
                r = rule_by_id(rs, h["rule_id"])
                if not r:
                    R.err(f"{p.name}: {h['rule_id']} 不在规则集中")
                elif r["type"] != typ or r["name"] != h["rule_name"]:
                    R.err(f"{p.name}: {h['rule_id']} 的分组或名称与规则文件不符")
                if len(h["evidence_tx_ids"]) > rs["evidence_limit"]:
                    R.err(f"{p.name}: {h['rule_id']} 证据超过 evidence_limit")
    if name == "make_ticket":
        check_ticket(obj, enums, rules, p.name)
    if name == "rejudge":
        ch, sm = obj["changed"], obj["summary"]
        if sm["changed"] != len(ch) or sum(sm["by_transition"].values()) != len(ch):
            R.err(f"{p.name}: summary.changed / by_transition 与 changed 列表不一致")
        up = sum(1 for c in ch if sev[c["new_status"]] > sev[c["old_status"]])
        if "upgraded" in sm and (sm["upgraded"], sm["downgraded"]) != (up, len(ch) - up):
            R.err(f"{p.name}: upgraded/downgraded 计数错误")
        for c in ch:
            d = "升级" if sev[c["new_status"]] > sev[c["old_status"]] else "降级"
            if c.get("direction") and c["direction"] != d:
                R.err(f"{p.name}: {c['acct_id']} direction 应为 {d}")
            if c["old_status"] == c["new_status"]:
                R.err(f"{p.name}: {c['acct_id']} 状态未变化却被列出")
        if [c["acct_id"] for c in ch] != sorted(c["acct_id"] for c in ch):
            R.err(f"{p.name}: changed 应按 acct_id 升序")
    if name == "trace_chain" and txs is not None:
        ref = reference_chains(acct, txs, rules[obj["rule_version"]][1])
        ref_by = {c["chain_id"]: c for c in ref}
        for c in obj["chains"]:
            r = ref_by.get(c["chain_id"])
            if not r:
                R.err(f"{p.name}: 参考实现未得到链 {c['chain_id']}（参考结果 {list(ref_by)}）")
                continue
            for k in ("hops", "total_amount", "duration_minutes"):
                if c[k] != r[k]:
                    R.err(f"{p.name}: {c['chain_id']}.{k} = {c[k]}，参考实现 = {r[k]}")
            if not c.get("truncated"):
                for k in ("tx_ids", "accounts", "roles"):
                    if k in c and c[k] != r[k]:
                        R.err(f"{p.name}: {c['chain_id']}.{k} 与参考实现不一致：{r[k]}")
            for e in c["edges"]:
                t = tx_by.get(e["tx_id"])
                if t and (t["from_acct"], t["to_acct"], t["time"], float(t["amount"])) != \
                        (e["from_acct"], e["to_acct"], e["time"], float(e["amount"])):
                    R.err(f"{p.name}: 边 {e['tx_id']} 与交易表不一致")


def check_tickets(tk_dir: Path, enums, rules, schemas, registry, tx_ids):
    R.start(f"工单 {tk_dir}")
    n = 0
    for p in sorted(tk_dir.glob("*.json")):
        tk = load_json(p)
        for e in schema_errors(schemas, registry, "make_ticket", tk):
            R.err(f"{p.name}: {e}")
        check_ticket(tk, enums, rules, p.name)
        t_ids, _ = set(), set()
        collect_ids(tk, t_ids, set())
        for x in sorted(t_ids - tx_ids):
            R.err(f"{p.name}: 交易 {x} 不存在")
        n += 1
    R.ok(f"{n} 份工单")


# ---------------------------------------------------------------- 7 防泄题
LEAK = re.compile(r"""(["'/\\]eval["'/\\]|answer(_tx)?\.csv|EVAL_DIR)""")


def check_leak(dirs):
    R.start("防泄题扫描")
    allowed = {"evaluate.py", "selfcheck.py", "gen_data.py", "import_amlsim.py"}
    n = 0
    for d in dirs:
        for p in Path(d).rglob("*.py"):
            if p.name in allowed:
                continue
            n += 1
            for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if LEAK.search(line) and not line.lstrip().startswith("#"):
                    R.err(f"{p}:{i}: 引用了 eval/ 或答案文件：{line.strip()[:80]}")
    R.ok(f"扫描 {n} 个文件")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, help="数据目录（含 accounts.csv、transactions.csv、dataset_meta.json）")
    ap.add_argument("--eval", type=Path, help="答案目录（含 answer.csv，可选 answer_tx.csv）")
    ap.add_argument("--fixtures", type=Path, help="fixtures 目录（如 core/fixtures）")
    ap.add_argument("--tickets", type=Path, help="工单目录（如 tickets/v1）")
    ap.add_argument("--check-leak", nargs="+", metavar="DIR", help="扫描这些目录的 .py 是否引用 eval/")
    ap.add_argument("--print-diff", nargs=2, metavar=("OLD", "NEW"), help="打印两个规则版本的差异 JSON")
    ap.add_argument("--skip-spec", action="store_true", help="跳过规范自身与 examples 的校验")
    a = ap.parse_args()

    enums, dschema, profile, rules, schemas, registry = load_spec()
    if a.print_diff:
        print(json.dumps(rules_diff(rules[a.print_diff[0]][1], rules[a.print_diff[1]][1]), ensure_ascii=False, indent=2))
        return 0
    if not a.skip_spec:
        check_enums(enums, schemas)
        check_rules(enums, rules, schemas, registry)
        check_profile(profile, rules)
        ex = SPEC / "examples"
        acct, txs, _ = check_dataset(ex / "data", ex / "eval", enums, dschema, schemas, registry)
        check_fixtures(ex / "fixtures", enums, rules, schemas, registry, acct, txs)
    acct = txs = None
    if a.data:
        acct, txs, _ = check_dataset(a.data, a.eval, enums, dschema, schemas, registry)
    if a.fixtures:
        check_fixtures(a.fixtures, enums, rules, schemas, registry, acct, txs)
    if a.tickets:
        if txs is None:
            R.start("工单")
            R.err("--tickets 需要同时给出 --data")
        else:
            check_tickets(a.tickets, enums, rules, schemas, registry, {t["tx_id"] for t in txs})
    if a.check_leak:
        check_leak(a.check_leak)

    print(f"\n结果：{len(R.errors)} 个错误，{len(R.warnings)} 个警告")
    return 1 if R.errors else 0


if __name__ == "__main__":
    sys.exit(main())
