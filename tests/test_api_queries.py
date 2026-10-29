"""get_account / get_transactions 的契约与正确性测试。

运行（仓库根目录）：python -m pytest tests -q
正确性用“另一条路径”核对：直接逐行读 CSV 暴力统计，不复用 core.store 的索引。
"""
import csv
import json
from collections import defaultdict

import pytest

from core import api
from conftest import FIXTURES, ROOT


def _raw(data_dir):
    with open(data_dir / "accounts.csv", encoding="utf-8", newline="") as f:
        accts = {r["acct_id"]: r for r in csv.DictReader(f)}
    with open(data_dir / "transactions.csv", encoding="utf-8", newline="") as f:
        txs = list(csv.DictReader(f))
    return accts, txs


def _brute_account(acct_id, txs):
    ins = [t for t in txs if t["to_acct"] == acct_id]
    outs = [t for t in txs if t["from_acct"] == acct_id]
    cps = {t["from_acct"] for t in ins} | {t["to_acct"] for t in outs}
    cps.discard("CASH")
    allt = sorted(ins + outs, key=lambda t: (t["time"], t["tx_id"]))
    return {
        "in_count": len(ins), "in_amount": sum(int(t["amount"]) for t in ins),
        "out_count": len(outs), "out_amount": sum(int(t["amount"]) for t in outs),
        "counterparty_count": len(cps),
        "first_tx_time": allt[0]["time"] if allt else None,
        "last_tx_time": allt[-1]["time"] if allt else None,
    }


# ------------------------------------------------------------ 与 fixtures 自洽（样例数据）
def test_matches_fixtures_on_example_data(example_data):
    fx = lambda n: json.loads((FIXTURES / n).read_text(encoding="utf-8"))
    assert api.get_account("A0087") == fx("get_account.json")
    assert api.get_transactions("A0087") == fx("get_transactions.json")
    assert api.get_account("A9999") == fx("error.json")


# ------------------------------------------------------------ 正式数据：全量核对
def test_get_account_all_300_match_bruteforce(real_data, validator):
    accts, txs = _raw(ROOT / "data")
    assert len(accts) == 300
    v = validator("get_account")
    for a, row in accts.items():
        got = api.get_account(a)
        v.validate(got)
        exp = _brute_account(a, txs)
        assert {k: got[k] for k in exp} == exp, a
        assert (got["name"], got["acct_type"], got["open_date"]) == (row["name"], row["acct_type"], row["open_date"])


def test_get_transactions_all_300_match_bruteforce(real_data, validator):
    accts, txs = _raw(ROOT / "data")
    v = validator("get_transactions")
    by = defaultdict(list)
    for t in txs:
        by[t["from_acct"]].append(t)
        by[t["to_acct"]].append(t)
    for a in accts:
        got = api.get_transactions(a, limit=200)
        v.validate(got)
        exp = sorted(by[a], key=lambda t: (t["time"], t["tx_id"]))
        assert got["total"] == len(exp)
        assert [t["tx_id"] for t in got["transactions"]] == [t["tx_id"] for t in exp[:200]], a
        assert got["truncated"] == (len(exp) > 200)
        for t in got["transactions"]:
            assert t["direction"] == ("转出" if t["from_acct"] == a else "转入")


def test_account_balance_identity(real_data):
    """全局守恒：所有账户转入合计 + 现金出口外的转出一致。"""
    tot_in = tot_out = 0
    for a in real_data.accounts:
        r = api.get_account(a)
        tot_in += r["in_amount"]
        tot_out += r["out_amount"]
    cash = sum(t["amount"] for t in real_data.transactions if t["to_acct"] == "CASH")
    assert tot_out - cash == tot_in


# ------------------------------------------------------------ 已知锚点（来自第 2 天人工核对的 C07 链）
def test_known_chain_c07_anchor(real_data):
    r = api.get_transactions("A0283", start="2026-03-05 00:00", end="2026-03-05 23:59")
    ins = {(t["from_acct"], t["amount"], t["time"]) for t in r["transactions"] if t["direction"] == "转入"}
    assert ("A0044", 35710, "2026-03-05 14:28") in ins
    assert ("A0287", 36059, "2026-03-05 14:33") in ins


def test_a0209_hand_counted(real_data):
    """手工从 transactions.csv 逐行数出的结果，与实现无关。"""
    r = api.get_account("A0209")
    assert (r["in_count"], r["in_amount"], r["out_count"], r["out_amount"], r["counterparty_count"]) == (6, 75241, 9, 72356, 14)
    assert (r["first_tx_time"], r["last_tx_time"]) == ("2026-03-01 09:14", "2026-03-07 21:54")


def test_merchant_has_many_transactions_and_truncates(real_data):
    r = api.get_transactions("A0074", limit=10)
    assert r["count"] == 10 and r["total"] > 10 and r["truncated"] is True


# ------------------------------------------------------------ 时间范围
def test_time_range_is_closed_interval(real_data):
    allr = api.get_transactions("A0283", limit=200)["transactions"]
    t0 = allr[0]["time"]
    r = api.get_transactions("A0283", start=t0, end=t0)
    assert r["total"] >= 1 and all(t["time"] == t0 for t in r["transactions"])
    assert r["start"] == t0 and r["end"] == t0


def test_empty_range_returns_zero_not_error(real_data, validator):
    r = api.get_transactions("A0283", start="2025-01-01 00:00", end="2025-01-02 00:00")
    validator("get_transactions").validate(r)
    assert (r["total"], r["count"], r["truncated"], r["transactions"]) == (0, 0, False, [])


def test_blank_time_means_unbounded(real_data):
    a = api.get_transactions("A0283", start="", end=None)
    b = api.get_transactions("A0283")
    assert a == b and a["start"] is None


# ------------------------------------------------------------ 输入规范化与错误
@pytest.mark.parametrize("raw", ["a0044", "  A0044  "])
def test_acct_id_is_normalized(real_data, raw):
    assert api.get_account(raw)["acct_id"] == "A0044"
    assert api.get_transactions(raw)["acct_id"] == "A0044"


@pytest.mark.parametrize("fn", [api.get_account, api.get_transactions])
def test_not_found(real_data, validator, fn):
    r = fn("A9999")
    validator("error").validate(r)
    assert r == {"error": "账户不存在", "code": "ACCOUNT_NOT_FOUND", "detail": "A9999"}


@pytest.mark.parametrize("bad", ["", "   ", "A1", "B0044", "A0044;DROP", None, 44, ["A0044"]])
@pytest.mark.parametrize("fn", [api.get_account, api.get_transactions])
def test_bad_acct_id(real_data, validator, fn, bad):
    r = fn(bad)
    validator("error").validate(r)
    assert r["code"] == "BAD_PARAM"


@pytest.mark.parametrize("bad", ["2026-03-05", "2026-03-05 14:28:00", "2026-3-5 14:28", "2026-13-01 00:00",
                                 "2026-02-30 10:00", "2026-03-05T14:28", 20260305])
def test_bad_time_format(real_data, validator, bad):
    for kw in ({"start": bad}, {"end": bad}):
        r = api.get_transactions("A0044", **kw)
        validator("error").validate(r)
        assert r["code"] == "BAD_TIME_FORMAT"


def test_start_after_end(real_data):
    r = api.get_transactions("A0044", start="2026-03-06 00:00", end="2026-03-05 00:00")
    assert r["code"] == "BAD_PARAM"


@pytest.mark.parametrize("bad", [0, 201, -1, "50", 1.5, True])
def test_bad_limit(real_data, validator, bad):
    r = api.get_transactions("A0044", limit=bad)
    validator("error").validate(r)
    assert r["code"] == "BAD_PARAM"


def test_limit_none_uses_default(real_data):
    assert api.get_transactions("A0074", limit=None)["count"] == 50


def test_limit_bounds_ok(real_data):
    assert api.get_transactions("A0074", limit=1)["count"] == 1
    assert api.get_transactions("A0074", limit=200)["count"] == 200


# ------------------------------------------------------------ 可复现与不泄漏
def test_deterministic(real_data):
    for a in ("A0044", "A0209", "A0074"):
        assert json.dumps(api.get_account(a), ensure_ascii=False) == json.dumps(api.get_account(a), ensure_ascii=False)
        assert api.get_transactions(a, limit=200) == api.get_transactions(a, limit=200)


def test_returned_data_is_a_copy(real_data):
    r = api.get_transactions("A0044")
    r["transactions"][0]["amount"] = -1
    assert api.get_transactions("A0044")["transactions"][0]["amount"] != -1


def test_internal_error_is_caught(monkeypatch, real_data, validator):
    def boom():
        raise RuntimeError("x")
    monkeypatch.setattr(api, "get_store", boom)
    r = api.get_account("A0044")
    validator("error").validate(r)
    assert r["code"] == "INTERNAL"


def test_data_dir_missing_gives_internal_error(monkeypatch, tmp_path, validator):
    from core import store
    monkeypatch.setenv(store.DATA_DIR_ENV, str(tmp_path))
    store.reset_store()
    try:
        r = api.get_account("A0044")
        validator("error").validate(r)
        assert r["code"] == "INTERNAL"
    finally:
        store.reset_store()


def test_core_does_not_touch_answer_files():
    import re
    leak = re.compile(r"""(["'/\\]eval["'/\\]|answer(_tx)?\.csv|EVAL_DIR)""")
    for name in ("store.py", "api.py"):
        for i, line in enumerate((ROOT / "core" / name).read_text(encoding="utf-8").splitlines(), 1):
            assert not leak.search(line), f"{name}:{i}"
