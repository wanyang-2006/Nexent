"""Fixture protocol checks: python mcp_server/selftest.py [URL | --in-process]."""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

from fastmcp import Client


async def check(target, mode: str = "fixture") -> None:
    async with Client(target) as c:
        names = [t.name for t in await c.list_tools()]
        expected = {"hello", "get_account", "get_transactions", "trace_chain", "check_rules", "make_ticket", "get_ticket", "rejudge"}
        if not expected.issubset(names):
            raise RuntimeError(f"Missing tools: {expected - set(names)}")
        r = await c.call_tool("hello", {"name": "world"})
        if r.data != "hello world":
            raise RuntimeError(f"hello 返回值不对：{r.data!r}")
        checks = 1

        async def call(name, params):
            nonlocal checks
            result = await c.call_tool(name, params)
            if result.is_error or not isinstance(result.data, dict):
                raise RuntimeError(f"{name}: {result}")
            checks += 1
            return result.data

        for name in ("get_account", "get_transactions", "trace_chain", "check_rules", "make_ticket", "get_ticket"):
            result = await call(name, {"acct_id": "A0087"})
            assert "error" not in result and result["acct_id"] == "A0087", (name, result)
            if mode == "fixture" or name not in ("get_account", "get_transactions"):
                assert result["_demo"]["mode"] == "fixture"
            else:
                assert result["_demo"]["mode"] == "synthetic_dataset"
                assert result["_demo"]["dataset_id"]
        result = await call("rejudge", {"old": "v1", "new": "v2"})
        assert "error" not in result and result["summary"]["changed"] == 3
        result = await call("get_transactions", {"acct_id": "A0087", "limit": 2})
        if mode == "fixture":
            assert (result["total"], result["count"], result["truncated"]) == (4, 2, True)
        else:
            assert result["count"] <= 2 and result["_demo"]["mode"] == "synthetic_dataset"
        result = await call("get_transactions", {"acct_id": "A0087", "start": "2026-03-03 10:09", "end": "2026-03-03 10:52"})
        if mode == "fixture":
            assert [row["tx_id"] for row in result["transactions"]] == ["T00415", "T00431"]
        else:
            assert all("2026-03-03 10:09" <= row["time"] <= "2026-03-03 10:52" for row in result["transactions"])
        for name, params, code in (
            ("get_account", {"acct_id": "A9999"}, "ACCOUNT_NOT_FOUND"),
            ("get_account", {"acct_id": "../other"}, "BAD_PARAM"),
            ("get_transactions", {"acct_id": "A0087", "limit": 201}, "BAD_PARAM"),
            ("get_transactions", {"acct_id": "A0087", "start": "2026-02-30 12:00"}, "BAD_TIME_FORMAT"),
            ("check_rules", {"acct_id": "A0087", "rule_version": "v3"}, "BAD_RULE_VERSION"),
            ("check_rules", {"acct_id": "A0087", "rule_version": "v2"}, "BAD_PARAM"),
            ("trace_chain", {"acct_id": "A0087", "max_hops": 2}, "BAD_PARAM"),
            ("rejudge", {"old": "v2", "new": "v1"}, "BAD_PARAM"),
        ):
            result = await call(name, params)
            assert result.get("code") == code, (name, result)
        print(f"PASS: {len(expected)} tools; {checks} MCP calls including filtering and invalid inputs")


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8900/sse"
    try:
        if target == "--in-process":
            import server
            with tempfile.TemporaryDirectory() as directory:
                server.DEMO_TICKETS = Path(directory)
                asyncio.run(check(server.mcp, server.MODE))
        else:
            asyncio.run(check(target, os.getenv("MCP_MODE", "fixture")))
        return 0
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
