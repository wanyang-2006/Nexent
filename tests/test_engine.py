"""trace_chain / check_rules / make_ticket / rejudge 的契约与正确性测试。

运行（仓库根目录）：python -m pytest tests -q
核对方式：
- 样例数据（10 个账户）上与 Data and Rules/examples/fixtures 逐字段比对（工单的 conclusion 措辞除外）；
- 正式数据上，追链结果与 validate_spec.py 的参考实现 reference_chains 逐条比对（v1、v2）；
- 300 个账户 × 两个版本全部通过 schema 与工单语义检查。
本文件不读取答案目录。
"""
import importlib.util
import json

import pytest
import yaml

from core import api
from core.ruleset import load_enums
from conftest import FIXTURES, ROOT, SPEC


def _fx(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def vs():
    """按路径加载 validate_spec.py（取参考实现 reference_chains 与 check_ticket）。"""
    spec = importlib.util.spec_from_file_location("validate_spec_for_tests", SPEC / "validate_spec.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ------------------------------------------------------------ 样例数据：与 fixtures 一致
def test_trace_chain_equals_fixture(example_data, validator):
    got = api.trace_chain("A0087")
    validator("trace_chain").validate(got)
    assert got == _fx("trace_chain.json")


def test_check_rules_matches_fixture(example_data, validator):
    got = api.check_rules("A0087")
    validator("check_rules").validate(got)
    exp = _fx("check_rules.json")
    strip = lambda hs: [{k: v for k, v in h.items() if k != "detail"} for h in hs]   # detail 措辞允许不同
    assert strip(got["hits"]) == strip(exp["hits"])
    assert strip(got["counter"]) == strip(exp["counter"])
    assert got["counter"][0]["detail"] == exp["counter"][0]["detail"]


def test_make_ticket_matches_fixture(example_data, validator, tmp_path):
    got = api.make_ticket("A0087")
    validator("make_ticket").validate(got)
    exp = _fx("make_ticket.json")
    assert {k: v for k, v in got.items() if k != "conclusion"} == {k: v for k, v in exp.items() if k != "conclusion"}
    assert "L-T00412" in got["conclusion"]
    saved = tmp_path / "tickets" / "v1" / "A0087.json"
    assert json.loads(saved.read_text(encoding="utf-8")) == got


def test_rejudge_equals_fixture(example_data, validator):
    got = api.rejudge("v1", "v2")
    validator("rejudge").validate(got)
    assert got == _fx("rejudge.json")


# ------------------------------------------------------------ 正式数据：追链与参考实现一致
@pytest.mark.parametrize("version,expected_count", [("v1", 10), ("v2", 13)])
def test_chains_equal_reference(real_data, vs, version, expected_count):
    from core import trace
    acct = {a: r for a, r in real_data.accounts.items()}
    txs = [dict(t, amount=str(t["amount"])) for t in real_data.transactions]
    rs = yaml.safe_load((SPEC / "rules" / f"rules_{version}.yaml").read_text(encoding="utf-8"))
    ref = vs.reference_chains(acct, txs, rs)
    mine = trace.all_chains(real_data, version)
    assert [c["chain_id"] for c in mine] == [c["chain_id"] for c in ref]
    for m, r in zip(mine, ref):
        for k in ("hops", "total_amount", "duration_minutes", "accounts", "tx_ids", "roles"):
            assert m[k] == r[k], (m["chain_id"], k)
    # 设计值（CHANGELOG 1.0.0：v1 10 条；v2 12 条埋入链 + D3 一条）
    assert len(mine) == expected_count


def test_v2_demo_chain_only_in_v2(real_data):
    """C05 的一级收款端 A0176：v1 不在链上，v2 在链上（停留 71 分钟，介于两版窗口之间）。"""
    assert api.trace_chain("A0176", rule_version="v1")["chains"] == []
    assert api.trace_chain("A0176", rule_version="v2")["chains"]


def test_same_chain_from_any_member(real_data):
    for c in api.trace_chain("A0209", max_hops=10)["chains"]:
        for a in c["accounts"]:
            ids = [x["chain_id"] for x in api.trace_chain(a, max_hops=10)["chains"]]
            assert c["chain_id"] in ids


def test_max_hops_only_trims_edges(real_data):
    full = api.trace_chain("A0044", max_hops=10)["chains"]
    small = api.trace_chain("A0044", max_hops=1)["chains"]
    assert full and len(full) == len(small)
    for f, s in zip(full, small):
        for k in ("chain_id", "hops", "total_amount", "duration_minutes", "accounts", "tx_ids", "roles"):
            assert f[k] == s[k]
        assert len(s["edges"]) >= 2
        assert s["truncated"] == (len(s["edges"]) < len(f["edges"]))


# ------------------------------------------------------------ 正式数据：300 个账户 × 两个版本
@pytest.mark.parametrize("version", ["v1", "v2"])
def test_all_accounts_schema_and_ticket_semantics(real_data, validator, vs, version):
    from core import ticket
    banned = load_enums()["conclusion_banned_words"]
    rules = {v: (None, yaml.safe_load((SPEC / "rules" / f"rules_{v}.yaml").read_text(encoding="utf-8")))
             for v in ("v1", "v2")}
    enums = load_enums()
    errs_before = len(vs.R.errors)
    for a in sorted(real_data.accounts):
        validator("trace_chain").validate(api.trace_chain(a, rule_version=version))
        cr = api.check_rules(a, rule_version=version)
        validator("check_rules").validate(cr)
        for h in cr["hits"] + cr["counter"]:
            assert all(x in real_data.tx_by_id for x in h["evidence_tx_ids"]), (a, h["rule_id"])
        tk = ticket.ticket_result(real_data, a, version)       # 不落盘
        validator("make_ticket").validate(tk)
        vs.check_ticket(tk, enums, rules, a)
        assert not any(w in tk["conclusion"] for w in banned), a
        assert all(e["tx_id"] in real_data.tx_by_id for e in tk["supporting_evidence"]), a
    assert len(vs.R.errors) == errs_before, vs.R.errors[errs_before:]


def test_rejudge_consistency(real_data, validator):
    r = api.rejudge("v1", "v2")
    validator("rejudge").validate(r)
    s = r["summary"]
    assert s["total"] == 300 and s["changed"] == len(r["changed"]) == sum(s["by_transition"].values())
    assert s["upgraded"] + s["downgraded"] == s["changed"]
    assert [c["acct_id"] for c in r["changed"]] == sorted(c["acct_id"] for c in r["changed"])
    for c in r["changed"]:
        assert c["old_status"] != c["new_status"]
        assert c["old_status"] == api.make_ticket(c["acct_id"], "v1")["status"]
        assert c["new_status"] == api.make_ticket(c["acct_id"], "v2")["status"]


def test_design_expectations(real_data):
    """03 规范第 4 节“典型结果”的设计预期（以实测为准；失败时先看 eval/selfcheck_*.txt 再决定改规则还是改预期）。"""
    st = lambda a, v: api.make_ticket(a, v)["status"]
    assert (st("A0176", "v1"), st("A0176", "v2")) == ("存在风险信号", "建议人工复核")     # C05 一级收款端
    assert (st("A0104", "v1"), st("A0104", "v2")) == ("未见异常", "证据不足")             # D3 的 P
    assert st("A0105", "v1") == "未见异常"                                                # 领工资的员工
    assert st("A0074", "v1") == "证据不足"                                                # 高频商户
    assert st("A0209", "v1") == "建议人工复核"                                            # C07 的 L2


# ------------------------------------------------------------ 参数与错误
@pytest.mark.parametrize("call", [
    lambda: api.trace_chain("A0044", rule_version="v9"),
    lambda: api.check_rules("A0044", rule_version="x1"),
    lambda: api.make_ticket("A0044", rule_version=""),
    lambda: api.rejudge("v1", "v99"),
    lambda: api.rejudge(1, "v2"),
])
def test_bad_rule_version(real_data, validator, call):
    r = call()
    validator("error").validate(r)
    assert r["code"] == "BAD_RULE_VERSION"


@pytest.mark.parametrize("bad", [0, 11, -1, "4", 2.5, True])
def test_bad_max_hops(real_data, bad):
    assert api.trace_chain("A0044", max_hops=bad)["code"] == "BAD_PARAM"


@pytest.mark.parametrize("fn", [api.trace_chain, api.check_rules, api.make_ticket])
def test_account_errors(real_data, fn):
    assert fn("A9999")["code"] == "ACCOUNT_NOT_FOUND"
    assert fn("B1")["code"] == "BAD_PARAM"


def test_version_is_normalized(real_data):
    assert api.check_rules("a0209", rule_version=" V1 ") == api.check_rules("A0209")


def test_deterministic_and_copied(real_data):
    a = json.dumps(api.make_ticket("A0209", "v2"), ensure_ascii=False)
    b = json.dumps(api.make_ticket("A0209", "v2"), ensure_ascii=False)
    assert a == b
    r = api.check_rules("A0209")
    r["hits"].clear()
    assert api.check_rules("A0209")["hits"]


def test_tool_modules_do_not_import_answer_scripts():
    for name in ("api.py", "trace.py", "rules.py", "ticket.py", "rejudge.py", "ruleset.py", "store.py"):
        text = (ROOT / "core" / name).read_text(encoding="utf-8")
        for bad in ("evaluate", "selfcheck", "gen_data", "verify_injected_chains"):
            assert f"import {bad}" not in text and f"from .{bad}" not in text and f"core.{bad}" not in text, (name, bad)
