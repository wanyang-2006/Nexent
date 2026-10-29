"""规则文件与枚举的加载、通用小工具。trace.py、rules.py、ticket.py、rejudge.py 共用。

- 规则文件：Data and Rules/rules/rules_<版本>.yaml（02 规范第 1 节），按版本缓存，改 YAML 后需重启服务。
- 枚举：Data and Rules/enums.yaml（缺口代码说明、禁用词等）。
- 差异：rules_diff(old, new) 与 validate_spec.py 中的同名函数口径一致（02 规范 6.2 节）。

只读 Data and Rules/，不读答案目录。
"""
from __future__ import annotations

import functools
import re
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC_DIR = ROOT / "Data and Rules"
RULES_DIR = SPEC_DIR / "rules"
VERSION_RE = re.compile(r"^v\d+$", re.ASCII)
TIME_FMT = "%Y-%m-%d %H:%M"
_EPOCH = datetime(2000, 1, 1)


class RulesetNotFound(Exception):
    """规则版本不存在（api 层转成 BAD_RULE_VERSION）。"""


def norm_version(v) -> str | None:
    """'V1 ' → 'v1'；格式不对返回 None。"""
    if not isinstance(v, str):
        return None
    v = v.strip().lower()
    return v if VERSION_RE.match(v) else None


def list_versions() -> list[str]:
    vs = [p.stem.split("_", 1)[1] for p in RULES_DIR.glob("rules_v*.yaml")]
    return sorted((v for v in vs if VERSION_RE.match(v)), key=lambda v: int(v[1:]))


@functools.lru_cache(maxsize=None)
def load_ruleset(version: str) -> dict:
    p = RULES_DIR / f"rules_{version}.yaml"
    if not VERSION_RE.match(version or "") or not p.is_file():
        raise RulesetNotFound(version)
    rs = yaml.safe_load(p.read_text(encoding="utf-8"))
    if rs.get("version") != version:
        raise ValueError(f"{p.name} 的 version 字段为 {rs.get('version')}，与文件名不一致")
    return rs


@functools.lru_cache(maxsize=None)
def load_enums() -> dict:
    return yaml.safe_load((SPEC_DIR / "enums.yaml").read_text(encoding="utf-8"))


def active_rules(rs: dict) -> list[dict]:
    """state 不是 deprecated 的规则，按规则号数字升序。"""
    rules = [r for r in rs["rules"] if r.get("state", "active") != "deprecated"]
    return sorted(rules, key=lambda r: rule_sort_key(r["rule_id"]))


def rule_sort_key(rid: str):
    return (int(rid[1:]), rid)


def rule_by_id(rs: dict, rid: str) -> dict | None:
    return next((r for r in rs["rules"] if r["rule_id"] == rid), None)


def resolve_window(rs: dict) -> int:
    """追链时间窗 W：trace.window_from 指向的参数（v1 为 R01.window_min = 60）。"""
    rid, param = rs["trace"]["window_from"].split(".")
    r = rule_by_id(rs, rid)
    if r is None:
        raise KeyError(rs["trace"]["window_from"])
    return r["params"][param]


def gap_desc(code: str) -> str:
    for g in load_enums()["enums"]["gap_code"]:
        if g["code"] == code:
            return g["desc"]
    raise KeyError(code)


def status_info() -> dict:
    """{'未见异常': {'code': 'CLEAR', 'severity': 0, 'action': None}, ...}"""
    return {s["value"]: s for s in load_enums()["enums"]["status"]}


@functools.lru_cache(maxsize=65536)
def to_min(t: str) -> int:
    """'YYYY-MM-DD HH:MM' → 自 2000-01-01 起的分钟数（不受时区和夏令时影响）。"""
    return int((datetime.strptime(t, TIME_FMT) - _EPOCH).total_seconds() // 60)


def fmt_amount(x) -> str:
    """62000 → '62000'；1234.5 → '1234.5'。"""
    if isinstance(x, float) and x.is_integer():
        x = int(x)
    return str(x) if isinstance(x, int) else f"{x:.2f}".rstrip("0").rstrip(".")


def rules_diff(old: dict, new: dict) -> dict:
    """02 规范 6.2 节格式的差异，与 validate_spec.py 的 rules_diff 一致。"""
    o = {r["rule_id"]: r for r in old["rules"]}
    n = {r["rule_id"]: r for r in new["rules"]}
    changed = []
    for rid in sorted(set(o) & set(n), key=rule_sort_key):
        for k in ("level", "in_types", "out_types", "state"):
            if o[rid].get(k) != n[rid].get(k):
                changed.append({"rule_id": rid, "field": k, "old": o[rid].get(k), "new": n[rid].get(k)})
        for k in sorted(set(o[rid]["params"]) | set(n[rid]["params"])):
            if o[rid]["params"].get(k) != n[rid]["params"].get(k):
                changed.append({"rule_id": rid, "field": f"params.{k}",
                                "old": o[rid]["params"].get(k), "new": n[rid]["params"].get(k)})
    trace_changed = []
    wo, wn = resolve_window(old), resolve_window(new)
    if wo != wn:
        trace_changed.append({"field": "W", "old": wo, "new": wn, "reason": f"window_from={new['trace']['window_from']}"})
    for k in sorted(set(old["trace"]) | set(new["trace"])):
        if old["trace"].get(k) != new["trace"].get(k):
            trace_changed.append({"field": k, "old": old["trace"].get(k), "new": new["trace"].get(k)})
    return {"from": old["version"], "to": new["version"],
            "added": [{"rule_id": r, "name": n[r]["name"]} for r in sorted(set(n) - set(o), key=rule_sort_key)],
            "removed": [{"rule_id": r, "name": o[r]["name"]} for r in sorted(set(o) - set(n), key=rule_sort_key)],
            "changed": changed, "trace_changed": trace_changed}
