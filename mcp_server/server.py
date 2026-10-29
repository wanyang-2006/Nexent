"""Fundtrace MCP: existing fixtures first; core.api when explicitly enabled."""
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
FIXTURES = Path(os.getenv("MCP_FIXTURES_DIR", str(ROOT / "core" / "fixtures")))
DEMO_TICKETS = Path(os.getenv("MCP_DEMO_TICKETS_DIR", str(Path(__file__).resolve().parent / "demo_tickets")))
logger = logging.getLogger("fundtrace")

mcp = FastMCP(
    "fundtrace",
    instructions=(
        f"Current mode: {MODE}. In fixture mode results are FIXED SYNTHETIC EXAMPLES, "
        "not live analysis. Account tools support only A0087; rule results only v1; "
        "trace_chain only max_hops=4; rejudge only v1 to v2. "
        "Tell users that fixture results are demonstration data."
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
        path = ROOT / "tickets" / params["rule_version"] / f"{params['acct_id']}.json"
        result = _read_object(path) if path.is_file() else api.make_ticket(**params)
    else:
        result = getattr(api, name)(**params)
    if not isinstance(result, dict):
        raise ValueError("core.api must return a JSON object as specified")
    if name == "get_ticket" and "error" not in result:
        if result.get("acct_id") != params["acct_id"] or result.get("rule_version") != params["rule_version"]:
            raise ValueError("Ticket account or rule version mismatch")
    return result


def _call(name: str, **params: Any) -> dict[str, Any]:
    try:
        _validate(params)
        if MODE == "fixture":
            return _fixture(name, params)
        if MODE == "real":
            return _real(name, params)
        raise RequestError("INTERNAL", "MCP_MODE 只能为 fixture 或 real")
    except RequestError as exc:
        return {"error": str(exc), "code": exc.code, "detail": exc.detail}
    except ModuleNotFoundError as exc:
        logger.exception("Backend unavailable")
        return {"error": "真实后端尚未就绪；请先使用 MCP_MODE=fixture", "code": "INTERNAL", "detail": str(exc)}
    except Exception as exc:
        logger.exception("Tool %s failed", name)
        return {"error": "工具执行失败，请检查服务端日志", "code": "INTERNAL", "detail": type(exc).__name__}


@mcp.tool(name="hello", description="测试工具：返回问候语")
def hello(name: str) -> str:
    return f"hello {name}"


@mcp.tool(description="账户画像。fixture模式仅支持A0087，返回固定仿真样例。")
def get_account(acct_id: str) -> dict[str, Any]:
    return _call("get_account", acct_id=acct_id)


@mcp.tool(description="账户交易，按时间排序，闭区间筛选，limit为1至200；fixture仅支持A0087。")
def get_transactions(acct_id: str, start: str | None = None, end: str | None = None, limit: int = 50) -> dict[str, Any]:
    return _call("get_transactions", acct_id=acct_id, start=start, end=end, limit=limit)


@mcp.tool(description="资金链追踪。fixture仅提供A0087、v1、max_hops=4的固定结果。")
def trace_chain(acct_id: str, max_hops: int = 4, rule_version: str = "v1") -> dict[str, Any]:
    return _call("trace_chain", acct_id=acct_id, max_hops=max_hops, rule_version=rule_version)


@mcp.tool(description="规则命中与反向证据。fixture仅提供A0087、v1样例。")
def check_rules(acct_id: str, rule_version: str = "v1") -> dict[str, Any]:
    return _call("check_rules", acct_id=acct_id, rule_version=rule_version)


@mcp.tool(description="生成研判工单。fixture仅A0087/v1，样例落盘到mcp_server/demo_tickets，与真实工单隔离。")
def make_ticket(acct_id: str, rule_version: str = "v1") -> dict[str, Any]:
    return _call("make_ticket", acct_id=acct_id, rule_version=rule_version)


@mcp.tool(description="获取研判工单。真实模式读取tickets，缺失时生成；fixture返回并保存固定样例。")
def get_ticket(acct_id: str, rule_version: str = "v1") -> dict[str, Any]:
    return _call("get_ticket", acct_id=acct_id, rule_version=rule_version)


@mcp.tool(description="比较规则版本重判结果。fixture仅返回v1到v2的10账户固定样例，非全量真实重判。")
def rejudge(old: str = "v1", new: str = "v2") -> dict[str, Any]:
    return _call("rejudge", old=old, new=new)


if __name__ == "__main__":
    if MODE not in ("fixture", "real"):
        raise SystemExit("MCP_MODE must be fixture or real")
    if MODE == "fixture":
        for tool_name in ("get_account", "get_transactions", "trace_chain", "check_rules", "make_ticket", "rejudge"):
            _read_object(FIXTURES / f"{tool_name}.json")
    elif importlib.util.find_spec("core.api") is None:
        raise SystemExit("core/api.py is missing; use MCP_MODE=fixture until the backend is ready")
    transport = os.getenv("MCP_TRANSPORT", "sse")
    if transport not in ("sse", "streamable-http"):
        raise SystemExit(f"MCP_TRANSPORT 只能是 sse 或 streamable-http，当前为 {transport!r}")
    mcp.run(
        show_banner=False,
        transport=transport,
        host=os.getenv("MCP_HOST", "0.0.0.0"),   # Nexent 在容器里，必须监听 0.0.0.0 才能访问
        port=int(os.getenv("MCP_PORT", "8900")),
    )
