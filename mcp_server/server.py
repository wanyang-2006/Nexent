"""Fundtrace MCP: fixture, hybrid query, or full core.api mode."""
from __future__ import annotations

import importlib
import json
import logging
import os
from pathlib import Path
import re
import sys
from datetime import datetime
from typing import Any

from fastmcp import FastMCP

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODE = os.getenv("MCP_MODE", "fixture" if os.getenv("USE_STUB", "1") == "1" else "real")
HYBRID_API_TOOLS = {"get_account", "get_transactions"}
FIXTURES = Path(os.getenv("MCP_FIXTURES_DIR", str(ROOT / "core" / "fixtures")))
DEMO_TICKETS = Path(os.getenv("MCP_DEMO_TICKETS_DIR", str(Path(__file__).resolve().parent / "demo_tickets")))
logger = logging.getLogger("fundtrace")

mcp = FastMCP(
    "fundtrace",
    instructions=(
        f"Current mode: {MODE}. In fixture mode all business results are fixed synthetic examples. "
        "In hybrid mode get_account and get_transactions query the full generated synthetic dataset "
        "and identify the dataset in _demo; trace_chain, check_rules, make_ticket, get_ticket, and "
        "rejudge remain fixed A0087/v1 or v1-to-v2 fixtures. Never combine a hybrid query for one "
        "account with the A0087 fixture chain, rules, or ticket as if they were one analysis. "
        "These are synthetic data, not live bank data."
        " In real mode ALL business tools run core.api over the generated dataset; v1 and v2 "
        "are supported, rejudge covers all accounts, and fixture examples must never be used "
        "as expected results. Real means computed algorithms, NOT real bank records."
    ),
)


class RequestError(Exception):
    def __init__(self, code: str, message: str, detail: str = ""):
        super().__init__(message)
        self.code = code
        self.detail = detail


def _validate(params: dict[str, Any]) -> None:
    acct = params.get("acct_id")
    if acct is not None and not re.fullmatch(r"A\d{4,}", acct):
        raise RequestError("BAD_PARAM", "账户编号格式应为 A 加至少四位数字", acct)
    for key in ("rule_version", "old", "new"):
        if key in params and params[key] not in ("v1", "v2"):
            raise RequestError("BAD_RULE_VERSION", "规则版本仅支持 v1、v2", str(params[key]))
    for key, upper in (("limit", 200), ("max_hops", 10)):
        if key in params:
            value = params[key]
            if type(value) is not int or not 1 <= value <= upper:
                raise RequestError("BAD_PARAM", f"{key} 必须是 1 至 {upper} 的整数")
    for key in ("start", "end"):
        value = params.get(key)
        if value is not None:
            try:
                parsed = datetime.strptime(value, "%Y-%m-%d %H:%M")
                if parsed.strftime("%Y-%m-%d %H:%M") != value:
                    raise ValueError(value)
            except ValueError:
                raise RequestError("BAD_TIME_FORMAT", "时间格式应为 YYYY-MM-DD HH:MM", value)
    if params.get("start") and params.get("end") and params["start"] > params["end"]:
        raise RequestError("BAD_PARAM", "start 不得晚于 end")
    if "old" in params and params["old"] == params["new"]:
        raise RequestError("BAD_PARAM", "重判的 old 和 new 必须不同")


def _read_object(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as handle:
        result = json.load(handle)
    if not isinstance(result, dict):
        raise ValueError(f"Expected JSON object: {path.name}")
    return result


def _fixture(name: str, params: dict[str, Any]) -> dict[str, Any]:
    source_name = "make_ticket" if name == "get_ticket" else name
    result = _read_object(FIXTURES / f"{source_name}.json")
    if "acct_id" in params and params["acct_id"] != result["acct_id"]:
        raise RequestError("ACCOUNT_NOT_FOUND", "样例集中没有该账户；不代表真实数据中不存在", params["acct_id"])
    if "rule_version" in params and params["rule_version"] != result["rule_version"]:
        raise RequestError("BAD_PARAM", "现有 fixture 只提供 v1 结果；v2 需接入真实后端")
    if name == "rejudge" and (params["old"], params["new"]) != (result["old"], result["new"]):
        raise RequestError("BAD_PARAM", "现有重判样例仅支持 v1 到 v2")
    if name == "trace_chain" and params["max_hops"] != result["max_hops"]:
        raise RequestError("BAD_PARAM", "固定追链样例仅支持 max_hops=4；其他深度需真实后端")
    if name == "get_transactions":
        rows = sorted(result["transactions"], key=lambda row: (row["time"], row["tx_id"]))
        start, end = params["start"], params["end"]
        rows = [row for row in rows if (start is None or row["time"] >= start) and (end is None or row["time"] <= end)]
        total = len(rows)
        rows = rows[:params["limit"]]
        result.update(start=start, end=end, total=total, count=len(rows), truncated=total > len(rows), transactions=rows)
    result["_demo"] = {
        "mode": "fixture",
        "source": f"core/fixtures/{source_name}.json" if FIXTURES == ROOT / "core" / "fixtures" else f"configured fixtures/{source_name}.json",
        "notice": "固定仿真样例，仅供工具联调，不是对真实账户的实时计算；重判样例覆盖10个样例账户。",
    }
    if name in ("make_ticket", "get_ticket"):
        DEMO_TICKETS.mkdir(parents=True, exist_ok=True)
        path = DEMO_TICKETS / params["rule_version"] / f"{params['acct_id']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def _real(name: str, params: dict[str, Any]) -> dict[str, Any]:
    api = importlib.import_module("core.api")
    if name == "get_ticket":
        from core.ticket import ticket_dir

        path = ticket_dir() / params["rule_version"] / f"{params['acct_id']}.json"
        result = _read_object(path) if path.is_file() else api.make_ticket(**params)
    else:
        result = getattr(api, name)(**params)
    if not isinstance(result, dict):
        raise ValueError("core.api must return a JSON object as specified")
    if name == "get_ticket" and "error" not in result:
        if result.get("acct_id") != params["acct_id"] or result.get("rule_version") != params["rule_version"]:
            raise ValueError("Ticket account or rule version mismatch")
    if "error" not in result:
        result = dict(result, _demo=_dataset_marker())
    return result


def _dataset_marker() -> dict[str, Any]:
    from core.store import get_store

    return {
        "mode": "synthetic_dataset",
        "dataset_id": get_store().dataset_id,
        "backend_mode": MODE,
        "source": "configured dataset" if os.getenv("FUNDTRACE_DATA_DIR") else "data/accounts.csv and data/transactions.csv",
        "notice": (
            "基于完整合成数据集及指定规则版本计算，不是真实银行数据，不是固定样例。"
            if MODE == "real" else
            "基于完整合成数据集计算，不是真实银行数据；其他分析工具仍返回固定样例，不可拼接为同一账户研判。"
        ),
    }


def _hybrid(name: str, params: dict[str, Any]) -> dict[str, Any]:
    if name not in HYBRID_API_TOOLS:
        return _fixture(name, params)
    api = importlib.import_module("core.api")
    result = getattr(api, name)(**params)
    if not isinstance(result, dict):
        raise ValueError("core.api must return a JSON object as specified")
    if "error" not in result:
        result["_demo"] = _dataset_marker()
    return result


def _call(name: str, **params: Any) -> dict[str, Any]:
    try:
        _validate(params)
        if MODE == "fixture":
            return _fixture(name, params)
        if MODE == "real":
            return _real(name, params)
        if MODE == "hybrid":
            return _hybrid(name, params)
        raise RequestError("INTERNAL", "MCP_MODE 只能为 fixture、hybrid 或 real")
    except RequestError as exc:
        return {"error": str(exc), "code": exc.code, "detail": exc.detail}
    except ModuleNotFoundError as exc:
        logger.exception("Backend unavailable")
        return {"error": "所需后端不可用；可切回 MCP_MODE=fixture 使用固定样例", "code": "INTERNAL", "detail": str(exc)}
    except Exception as exc:
        logger.exception("Tool %s failed", name)
        return {"error": "工具执行失败，请检查服务端日志", "code": "INTERNAL", "detail": type(exc).__name__}


@mcp.tool(name="hello", description="测试工具：返回问候语")
def hello(name: str) -> str:
    return f"hello {name}"


@mcp.tool(description="账户画像。fixture模式返回A0087固定样例；hybrid模式查询完整合成数据集，结果含数据集标记。")
def get_account(acct_id: str) -> dict[str, Any]:
    return _call("get_account", acct_id=acct_id)


@mcp.tool(description="账户交易，按时间排序，闭区间筛选，limit为1至200；hybrid模式查询完整合成数据集。")
def get_transactions(acct_id: str, start: str | None = None, end: str | None = None, limit: int = 50) -> dict[str, Any]:
    return _call("get_transactions", acct_id=acct_id, start=start, end=end, limit=limit)


@mcp.tool(description="资金链追踪。real模式按合成数据及v1/v2规则计算，max_hops为1至10；fixture/hybrid仅A0087、v1、深度4固定样例。")
def trace_chain(acct_id: str, max_hops: int = 4, rule_version: str = "v1") -> dict[str, Any]:
    return _call("trace_chain", acct_id=acct_id, max_hops=max_hops, rule_version=rule_version)


@mcp.tool(description="规则命中与反向证据。real模式按合成数据及v1/v2计算；fixture/hybrid仅A0087/v1固定样例。")
def check_rules(acct_id: str, rule_version: str = "v1") -> dict[str, Any]:
    return _call("check_rules", acct_id=acct_id, rule_version=rule_version)


@mcp.tool(description="生成并保存研判工单。real模式按指定账户、v1/v2计算；fixture/hybrid仅A0087/v1固定样例。")
def make_ticket(acct_id: str, rule_version: str = "v1") -> dict[str, Any]:
    return _call("make_ticket", acct_id=acct_id, rule_version=rule_version)


@mcp.tool(description="获取研判工单。fixture/hybrid返回并保存A0087/v1固定样例；real模式读取真实工单或调用后端。")
def get_ticket(acct_id: str, rule_version: str = "v1") -> dict[str, Any]:
    return _call("get_ticket", acct_id=acct_id, rule_version=rule_version)


@mcp.tool(description="比较规则版本重判结果。real模式对合成数据全部账户按old/new计算；fixture/hybrid仅v1到v2的10账户固定样例。")
def rejudge(old: str = "v1", new: str = "v2") -> dict[str, Any]:
    return _call("rejudge", old=old, new=new)


if __name__ == "__main__":
    if MODE not in ("fixture", "hybrid", "real"):
        raise SystemExit("MCP_MODE must be fixture, hybrid, or real")
    if MODE in ("fixture", "hybrid"):
        for tool_name in ("get_account", "get_transactions", "trace_chain", "check_rules", "make_ticket", "rejudge"):
            _read_object(FIXTURES / f"{tool_name}.json")
    if MODE in ("hybrid", "real") and importlib.util.find_spec("core.api") is None:
        raise SystemExit("core/api.py is missing; use MCP_MODE=fixture until the backend is ready")
    if MODE in ("hybrid", "real"):
        try:
            from core.store import get_store

            store = get_store()
            if not store.accounts or not store.transactions or not store.dataset_id:
                raise ValueError("synthetic dataset has no accounts or transactions")
            api = importlib.import_module("core.api")
            required = HYBRID_API_TOOLS if MODE == "hybrid" else (
                "get_account", "get_transactions", "trace_chain", "check_rules", "make_ticket", "rejudge"
            )
            for name in required:
                if not callable(getattr(api, name, None)):
                    raise ValueError(f"core.api.{name} is missing")
            if MODE == "real":
                from core.ruleset import load_enums, load_ruleset

                load_enums()
                for version in ("v1", "v2"):
                    load_ruleset(version)
        except Exception as exc:
            raise SystemExit(f"{MODE} backend preflight failed: {exc}") from exc
    transport = os.getenv("MCP_TRANSPORT", "sse")
    if transport not in ("sse", "streamable-http"):
        raise SystemExit(f"MCP_TRANSPORT 只能是 sse 或 streamable-http，当前为 {transport!r}")
    mcp.run(
        show_banner=False,
        transport=transport,
        host=os.getenv("MCP_HOST", "0.0.0.0"),   # Nexent 在容器里，必须监听 0.0.0.0 才能访问
        port=int(os.getenv("MCP_PORT", "8900")),
    )
