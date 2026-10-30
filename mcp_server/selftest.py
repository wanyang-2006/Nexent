"""Fixture protocol checks: python mcp_server/selftest.py [URL | --in-process]."""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

from fastmcp import Client


async def check_real(target) -> None:
    async with Client(target) as client:
        names = {tool.name for tool in await client.list_tools()}
        assert names == {"hello", "get_account", "get_transactions", "trace_chain", "check_rules", "make_ticket", "get_ticket", "rejudge"}
        checks = 0

        async def call(name, params, code=None):
            nonlocal checks
            response = await client.call_tool(name, params)
            assert not response.is_error and isinstance(response.data, dict), response
            result = response.data
            if code:
                assert result.get("code") == code, result
            else:
                assert "error" not in result, result
                assert result["_demo"]["mode"] == "synthetic_dataset", result
                assert result["_demo"]["backend_mode"] == "real", result
                assert result["_demo"]["dataset_id"]
            checks += 1
            return result

        assert (await client.call_tool("hello", {"name": "world"})).data == "hello world"
        checks += 1
        await call("get_account", {"acct_id": "A0044"})
        txs = await call("get_transactions", {"acct_id": "A0044", "start": "2026-03-01 11:00", "end": "2026-03-02 00:00", "limit": 5})
        assert [t["tx_id"] for t in txs["transactions"]] == ["T00121", "T00224", "T00365"]
        assert (txs["total"], txs["count"], txs["truncated"]) == (3, 3, False)
        for version in ("v1", "v2"):
            params = {"acct_id": "A0176", "rule_version": version}
            chain = await call("trace_chain", dict(params, max_hops=4))
            assert bool(chain["chains"]) == (version == "v2")
            await call("check_rules", params)
            ticket = await call("make_ticket", params)
            assert ticket["status_code"] == ("RISK_SIGNAL" if version == "v1" else "REVIEW")
            assert await call("get_ticket", params) == ticket
        result = await call("rejudge", {"old": "v1", "new": "v2"})
        assert result["summary"]["total"] == 300
        assert result["summary"]["changed"] == len(result["changed"]) > 0
        assert "A0176" in {row["acct_id"] for row in result["changed"]}
        for name, params, code in (
            ("get_account", {"acct_id": "A9999"}, "ACCOUNT_NOT_FOUND"),
            ("get_ticket", {"acct_id": "A9999"}, "ACCOUNT_NOT_FOUND"),
            ("get_account", {"acct_id": "../other"}, "BAD_PARAM"),
            ("get_transactions", {"acct_id": "A0044", "limit": 201}, "BAD_PARAM"),
            ("get_transactions", {"acct_id": "A0044", "start": "2026-02-30 12:00"}, "BAD_TIME_FORMAT"),
            ("check_rules", {"acct_id": "A0176", "rule_version": "v99"}, "BAD_RULE_VERSION"),
            ("trace_chain", {"acct_id": "A0176", "max_hops": 11}, "BAD_PARAM"),
        ):
            await call(name, params, code)
        print(f"PASS: 8 tools; {checks} MCP calls; real algorithms on synthetic dataset")


async def check(target, mode: str = "fixture") -> None:
    if mode == "real":
        await check_real(target)
        return
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
                os.environ["FUNDTRACE_TICKET_DIR"] = directory
                asyncio.run(check(server.mcp, server.MODE))
        else:
            asyncio.run(check(target, os.getenv("MCP_MODE", "fixture")))
        return 0
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
