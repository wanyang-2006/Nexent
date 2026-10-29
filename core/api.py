"""六个核心函数中的两个查询函数：get_account、get_transactions。

契约见 Data and Rules/03_判定与输出规范.md 第 1、2 节与 schemas/*.schema.json。
- 一律返回 dict，不抛异常；出错返回 {"error", "code", "detail"}。
- 同一数据、同一参数，输出逐字节相同（交易按 (time, tx_id) 升序）。
- 账户号会先去掉首尾空白并转大写（"a0087 " 等同 "A0087"），再做格式校验。

追链、规则、工单、重判（trace_chain / check_rules / make_ticket / rejudge）在后续文件中实现，
并在此处导出。
"""
from __future__ import annotations

import functools
import re
from datetime import datetime

from .store import CASH, get_store

ACCT_RE = re.compile(r"^A\d{4,}$", re.ASCII)
TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$", re.ASCII)
LIMIT_MIN, LIMIT_MAX, LIMIT_DEFAULT = 1, 200, 50

ERROR_TEXT = {
    "ACCOUNT_NOT_FOUND": "账户不存在",
    "BAD_RULE_VERSION": "规则版本不存在",
    "BAD_TIME_FORMAT": "时间格式应为 YYYY-MM-DD HH:MM",
    "BAD_PARAM": "参数取值不合法",
    "INTERNAL": "内部错误",
}


def error(code: str, detail: str | None = None) -> dict:
    out = {"error": ERROR_TEXT[code], "code": code}
    if detail is not None:
        out["detail"] = str(detail)
    return out


def guarded(fn):
    """把未预期的异常转成 INTERNAL 错误，保证工具永不抛异常。"""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            return error("INTERNAL", f"{type(e).__name__}: {e}")
    return wrapper


def _norm_acct(acct_id):
    """返回 (规范化账户号, None) 或 (None, 错误字典)。"""
    if not isinstance(acct_id, str) or not acct_id.strip():
        return None, error("BAD_PARAM", "acct_id 必须是非空字符串，格式如 A0087")
    a = acct_id.strip().upper()
    if not ACCT_RE.match(a):
        return None, error("BAD_PARAM", f"账户号格式应为 A 加 4 位以上数字，收到 {acct_id!r}")
    return a, None


def _check_time(value, name: str):
    """None 或空串表示不限；否则必须是 YYYY-MM-DD HH:MM 且是真实存在的时间。返回 (值, None) 或 (None, 错误)。"""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, None
    if not isinstance(value, str) or not TIME_RE.match(value.strip()):
        return None, error("BAD_TIME_FORMAT", f"{name}={value!r}")
    v = value.strip()
    try:
        datetime.strptime(v, "%Y-%m-%d %H:%M")
    except ValueError:
        return None, error("BAD_TIME_FORMAT", f"{name}={value!r} 不是有效时间")
    return v, None


def _direction(tx: dict, acct_id: str) -> str:
    return "转出" if tx["from_acct"] == acct_id else "转入"


def _view(tx: dict, acct_id: str) -> dict:
    return {"tx_id": tx["tx_id"], "time": tx["time"], "from_acct": tx["from_acct"], "to_acct": tx["to_acct"],
            "amount": tx["amount"], "tx_type": tx["tx_type"], "direction": _direction(tx, acct_id)}


@guarded
def get_account(acct_id: str) -> dict:
    """账户基本信息与全部交易的汇总统计（所有交易类型，提现计入转出；对手方去重且不含 CASH）。"""
    a, err = _norm_acct(acct_id)
    if err:
        return err
    st = get_store()
    if not st.has_account(a):
        return error("ACCOUNT_NOT_FOUND", a)
    acct = st.accounts[a]
    txs = st.account_txs(a)
    in_cnt = in_amt = out_cnt = out_amt = 0
    cps = set()
    for t in txs:
        if t["from_acct"] == a:
            out_cnt += 1
            out_amt += t["amount"]
            cps.add(t["to_acct"])
        else:
            in_cnt += 1
            in_amt += t["amount"]
            cps.add(t["from_acct"])
    cps.discard(CASH)
    return {
        "acct_id": a,
        "name": acct["name"],
        "acct_type": acct["acct_type"],
        "open_date": acct["open_date"],
        "in_count": in_cnt,
        "in_amount": in_amt,
        "out_count": out_cnt,
        "out_amount": out_amt,
        "counterparty_count": len(cps),
        "first_tx_time": txs[0]["time"] if txs else None,
        "last_tx_time": txs[-1]["time"] if txs else None,
    }


@guarded
def get_transactions(acct_id: str, start: str | None = None, end: str | None = None,
                     limit: int = LIMIT_DEFAULT) -> dict:
    """账户在 [start, end]（闭区间，格式 YYYY-MM-DD HH:MM，可省略）内的交易，按时间升序返回前 limit 条（1 至 200）。"""
    a, err = _norm_acct(acct_id)
    if err:
        return err
    s, err = _check_time(start, "start")
    if err:
        return err
    e, err = _check_time(end, "end")
    if err:
        return err
    if s and e and s > e:
        return error("BAD_PARAM", f"start={s} 晚于 end={e}")
    if limit is None:
        limit = LIMIT_DEFAULT
    if isinstance(limit, bool) or not isinstance(limit, int) or not LIMIT_MIN <= limit <= LIMIT_MAX:
        return error("BAD_PARAM", f"limit 应为 {LIMIT_MIN} 至 {LIMIT_MAX} 的整数，收到 {limit!r}")
    st = get_store()
    if not st.has_account(a):
        return error("ACCOUNT_NOT_FOUND", a)
    rows = [t for t in st.account_txs(a) if (not s or t["time"] >= s) and (not e or t["time"] <= e)]
    shown = rows[:limit]
    return {
        "acct_id": a,
        "start": s,
        "end": e,
        "total": len(rows),
        "count": len(shown),
        "truncated": len(rows) > len(shown),
        "transactions": [_view(t, a) for t in shown],
    }
