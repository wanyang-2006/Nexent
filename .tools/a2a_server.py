"""
Fundtrace A2A Server  —  northbound interface for the fundtrace MCP.

Implements the Google A2A (Agent-to-Agent) protocol v0.2:
  GET  /.well-known/agent.json  →  Agent Card
  POST /                        →  task/send  (JSON-RPC 2.0 envelope)
  POST /                        →  task/sendSubscribe  (SSE streaming)
  GET  /health                  →  {"status": "ok"}

Internal calls go through the official MCP Python SDK (mcp.client.sse).

Usage:
    MCP_URL=http://127.0.0.1:8900/sse uvicorn a2a_server:app --host 0.0.0.0 --port 8901
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re as _re
import uuid
from typing import Any, AsyncIterator

from mcp.client.sse import sse_client
from mcp import ClientSession
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

logger = logging.getLogger("a2a")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MCP_URL = os.getenv("MCP_URL", "http://127.0.0.1:8900/sse")
PUBLIC_URL = os.getenv("A2A_PUBLIC_URL", "http://60.205.124.241:8901")

# ---------------------------------------------------------------------------
# Agent Card
# ---------------------------------------------------------------------------
AGENT_CARD: dict[str, Any] = {
    "name": "Fundtrace Research Assistant",
    "description": (
        "涉诈资金链路研判助手 — anti-fraud fund-chain investigation agent. "
        "Accepts natural-language requests in Chinese or English and produces "
        "structured investigation tickets using synthetic transaction data."
    ),
    "url": PUBLIC_URL,
    "version": "1.0.0",
    "provider": {
        "organization": "Nexent / ICT Competition",
        "url": PUBLIC_URL,
    },
    "capabilities": {
        "streaming": True,
        "pushNotifications": False,
        "stateTransitionHistory": False,
    },
    "defaultInputModes": ["text/plain"],
    "defaultOutputModes": ["application/json", "text/plain"],
    "skills": [
        {
            "id": "fund-chain-investigation",
            "name": "资金链路研判",
            "description": (
                "Given an account ID (e.g. A0209) and optional rule version (v1 or v2), "
                "runs: get_account → trace_chain → check_rules → make_ticket and returns "
                "a full investigation ticket."
            ),
            "tags": ["fraud", "investigation", "finance"],
            "examples": ["请研判账户 A0209", "按 v2 研判账户 A0176"],
            "inputModes": ["text/plain"],
            "outputModes": ["application/json"],
        },
        {
            "id": "rule-rejudge",
            "name": "规则版本重判",
            "description": (
                "Compare v1 and v2 rule verdicts across all accounts via rejudge(), "
                "returning the list of accounts whose conclusion changed and why."
            ),
            "tags": ["rule-update", "rejudge"],
            "examples": ["规则升级到 v2 后哪些账户结论变了？"],
            "inputModes": ["text/plain"],
            "outputModes": ["application/json"],
        },
    ],
}

# ---------------------------------------------------------------------------
# MCP helper — uses official SDK
# ---------------------------------------------------------------------------

async def call_mcp_tool(tool: str, args: dict[str, Any]) -> Any:
    """Call a single MCP tool and return the parsed result dict."""
    async with sse_client(MCP_URL) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool, args)
            if result.is_error:
                content_text = result.content[0].text if result.content else "unknown error"
                return {"error": content_text, "code": "MCP_ERROR"}
            # Prefer structured_content, fall back to parsing text
            if result.structured_content:
                return result.structured_content
            if result.content and result.content[0].type == "text":
                try:
                    return json.loads(result.content[0].text)
                except json.JSONDecodeError:
                    return {"text": result.content[0].text}
            return {}


# ---------------------------------------------------------------------------
# Intent parsing
# ---------------------------------------------------------------------------

_ACCT_RE = _re.compile(r"A\d{4,}")
_VER_RE = _re.compile(r"\bv[12]\b")


def _parse_request(text: str) -> tuple[str | None, str]:
    accts = _ACCT_RE.findall(text)
    vers = _VER_RE.findall(text)
    acct = accts[0] if accts else None
    ver = vers[-1] if vers else "v1"
    return acct, ver


# ---------------------------------------------------------------------------
# Investigation pipeline
# ---------------------------------------------------------------------------

async def investigate_account(acct_id: str, rule_version: str) -> dict[str, Any]:
    steps: list[dict] = []

    async def step(name: str, tool: str, args: dict) -> Any:
        logger.info("step %s: %s(%s)", name, tool, args)
        result = await call_mcp_tool(tool, args)
        steps.append({"step": name, "tool": tool, "args": args, "result": result})
        return result

    account = await step("get_account", "get_account", {"acct_id": acct_id})
    if isinstance(account, dict) and "error" in account:
        return {"status": "error", "message": account["error"], "steps": steps}

    chain = await step("trace_chain", "trace_chain",
                       {"acct_id": acct_id, "max_hops": 4, "rule_version": rule_version})

    rules = await step("check_rules", "check_rules",
                       {"acct_id": acct_id, "rule_version": rule_version})

    ticket = await step("make_ticket", "make_ticket",
                        {"acct_id": acct_id, "rule_version": rule_version})

    return {
        "status": "completed",
        "acct_id": acct_id,
        "rule_version": rule_version,
        "account": account,
        "chain": chain,
        "rules": rules,
        "ticket": ticket,
        "steps": steps,
    }


async def run_rejudge(old: str = "v1", new: str = "v2") -> dict[str, Any]:
    logger.info("rejudge %s -> %s", old, new)
    result = await call_mcp_tool("rejudge", {"old": old, "new": new})
    return {"status": "completed", "rejudge": result}


# ---------------------------------------------------------------------------
# A2A task processor
# ---------------------------------------------------------------------------

async def _process_task(task_id: str, text: str) -> AsyncIterator[dict[str, Any]]:
    is_rejudge = any(kw in text for kw in
                     ["rejudge", "重判", "规则升级", "版本变化", "变化账户", "结论变化"])
    acct_id, rule_version = _parse_request(text)

    yield {
        "id": task_id,
        "status": {
            "state": "working",
            "message": {"role": "agent", "parts": [{"type": "text", "text": "正在处理请求..."}]},
        },
        "final": False,
    }

    try:
        if is_rejudge and acct_id is None:
            result = await run_rejudge()
        elif acct_id:
            result = await investigate_account(acct_id, rule_version)
        else:
            result = {
                "status": "error",
                "message": (
                    "未能识别账户编号（如 A0209）或研判意图。"
                    "请在请求中包含账户号，例如：请研判账户 A0209"
                ),
            }
    except Exception as exc:
        logger.exception("task %s failed: %s", task_id, exc)
        result = {"status": "error", "message": str(exc)}

    state = "failed" if result.get("status") == "error" else "completed"

    if state == "failed":
        summary = result.get("message", "Unknown error")
    elif "ticket" in result:
        ticket = result.get("ticket", {})
        conclusion = ticket.get("conclusion", "")
        summary = (
            f"研判完成：{result.get('acct_id', '')} "
            f"规则版本={result.get('rule_version', '')} "
            f"结论={conclusion}"
        )
    else:
        changed = result.get("rejudge", {}).get("summary", {}).get("changed", "?")
        summary = f"重判完成，共 {changed} 个账户结论变化"

    yield {
        "id": task_id,
        "status": {
            "state": state,
            "message": {
                "role": "agent",
                "parts": [
                    {"type": "text", "text": summary},
                    {"type": "data", "data": result},
                ],
            },
        },
        "final": True,
    }


# ---------------------------------------------------------------------------
# HTTP handlers
# ---------------------------------------------------------------------------

async def agent_card(request: Request) -> JSONResponse:
    return JSONResponse(AGENT_CARD)


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "mcp_url": MCP_URL})


async def tasks_endpoint(request: Request) -> Response:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None,
             "error": {"code": -32700, "message": "Parse error"}},
            status_code=400,
        )

    # Support plain shorthand: {"text": "..."}
    if "text" in body and "method" not in body:
        task_id = str(uuid.uuid4())
        final_event: dict | None = None
        async for event in _process_task(task_id, body["text"]):
            if event.get("final"):
                final_event = event
        return JSONResponse(final_event or {"id": task_id, "status": {"state": "failed"}})

    rpc_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})

    if method not in ("tasks/send", "tasks/sendSubscribe", "message/send"):
        return JSONResponse(
            {"jsonrpc": "2.0", "id": rpc_id,
             "error": {"code": -32601, "message": f"Method not found: {method}"}},
            status_code=404,
        )

    # Extract text from A2A message parts
    message = params.get("message") or {}
    parts = message.get("parts", []) if isinstance(message, dict) else []
    text = " ".join(p.get("text", "") for p in parts if p.get("type") == "text")
    if not text:
        text = params.get("text", "") or str(params)

    task_id = params.get("id") or str(uuid.uuid4())

    if method == "tasks/sendSubscribe":
        async def event_gen():
            async for event in _process_task(task_id, text):
                yield {"data": json.dumps(event, ensure_ascii=False)}
        return EventSourceResponse(event_gen())

    # Blocking collect
    final_event = None
    async for event in _process_task(task_id, text):
        if event.get("final"):
            final_event = event

    return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "result": final_event})


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

routes = [
    Route("/.well-known/agent.json", agent_card, methods=["GET"]),
    Route("/health", health, methods=["GET"]),
    Route("/", tasks_endpoint, methods=["POST"]),
]

middleware = [
    Middleware(CORSMiddleware,
               allow_origins=["*"],
               allow_methods=["GET", "POST"],
               allow_headers=["*"]),
]

app = Starlette(routes=routes, middleware=middleware)
