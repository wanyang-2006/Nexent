"""Contract, fixture integrity, and backend handoff checks without network."""
import json
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

import server


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.mode = patch.object(server, "MODE", "fixture")
        self.mode.start()
        self.addCleanup(self.mode.stop)
        self.tickets = patch.object(server, "DEMO_TICKETS", self.root / "demo_tickets")
        self.tickets.start()
        self.addCleanup(self.tickets.stop)

    def test_success_schema_and_source_integrity(self):
        schemas = server.ROOT / "Data and Rules" / "schemas"
        registry = Registry()
        for path in schemas.glob("*.schema.json"):
            schema = json.loads(path.read_text(encoding="utf-8"))
            registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
        for name in ("get_account", "get_transactions", "trace_chain", "check_rules", "make_ticket", "get_ticket", "rejudge"):
            with self.subTest(name=name):
                source = "make_ticket" if name == "get_ticket" else name
                params = {"old": "v1", "new": "v2"} if name == "rejudge" else {"acct_id": "A0087"}
                if name == "get_transactions":
                    params.update(start=None, end=None, limit=50)
                if name == "trace_chain":
                    params.update(max_hops=4, rule_version="v1")
                if name in ("check_rules", "make_ticket", "get_ticket"):
                    params["rule_version"] = "v1"
                path = server.FIXTURES / f"{source}.json"
                before = path.read_bytes()
                result = server._call(name, **params)
                self.assertNotIn("error", result)
                schema = json.loads((schemas / f"{source}.schema.json").read_text(encoding="utf-8"))
                Draft202012Validator(schema, registry=registry).validate(result)
                result.pop("_demo")
                self.assertEqual(result, json.loads(before))
                self.assertEqual(path.read_bytes(), before)

    def test_transaction_filter_and_empty_range(self):
        result = server._call("get_transactions", acct_id="A0087", start="2026-03-03 10:09", end="2026-03-03 10:52", limit=1)
        self.assertEqual((result["total"], result["count"], result["truncated"]), (2, 1, True))
        self.assertEqual(result["transactions"][0]["tx_id"], "T00415")
        result = server._call("get_transactions", acct_id="A0087", start="2026-04-01 00:00", end=None, limit=50)
        self.assertEqual((result["total"], result["count"], result["transactions"]), (0, 0, []))

    def test_validation(self):
        for params, code in (
            ({"acct_id": "../A0087"}, "BAD_PARAM"),
            ({"acct_id": "A9999"}, "ACCOUNT_NOT_FOUND"),
            ({"acct_id": "A0087", "limit": 0}, "BAD_PARAM"),
            ({"acct_id": "A0087", "limit": 201}, "BAD_PARAM"),
            ({"acct_id": "A0087", "limit": True}, "BAD_PARAM"),
            ({"acct_id": "A0087", "start": "2026-02-30 10:00"}, "BAD_TIME_FORMAT"),
            ({"acct_id": "A0087", "start": "2026-3-01 10:00"}, "BAD_TIME_FORMAT"),
            ({"acct_id": "A0087", "start": "2026-03-02 00:00", "end": "2026-03-01 00:00"}, "BAD_PARAM"),
        ):
            with self.subTest(params=params):
                defaults = dict(acct_id="A0087", start=None, end=None, limit=50)
                defaults.update(params)
                self.assertEqual(server._call("get_transactions", **defaults)["code"], code)
        for version, code in (("v2", "BAD_PARAM"), ("v3", "BAD_RULE_VERSION")):
            self.assertEqual(server._call("check_rules", acct_id="A0087", rule_version=version)["code"], code)

    def test_demo_ticket_persisted_outside_real_tickets(self):
        result = server._call("make_ticket", acct_id="A0087", rule_version="v1")
        path = self.root / "demo_tickets" / "v1" / "A0087.json"
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), result)
        self.assertEqual(server._call("get_ticket", acct_id="A0087", rule_version="v1"), result)
        self.assertFalse((self.root / "tickets").exists())

    def test_real_mode_delegates_and_reads_ticket(self):
        api = ModuleType("core.api")
        calls = []

        def make_ticket(**params):
            calls.append(params)
            return dict(params, ticket_id="test-ticket")

        api.make_ticket = make_ticket
        api.get_account = lambda **params: dict(params, marker="real")
        with patch.object(server, "MODE", "real"), patch.dict(os.environ, {"FUNDTRACE_TICKET_DIR": str(self.root / "tickets")}), patch.dict(sys.modules, {"core.api": api}):
            self.assertEqual(server._call("get_account", acct_id="A0087")["marker"], "real")
            result = server._call("get_ticket", acct_id="A0087", rule_version="v1")
            self.assertEqual(len(calls), 1)
            path = self.root / "tickets" / "v1" / "A0087.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(result), encoding="utf-8")
            self.assertEqual(server._call("get_ticket", acct_id="A0087", rule_version="v1"), result)
            self.assertEqual(len(calls), 1)
            path.write_text('{"acct_id":"A9999","rule_version":"v1"}', encoding="utf-8")
            with self.assertLogs("fundtrace", level="ERROR"):
                self.assertEqual(server._call("get_ticket", acct_id="A0087", rule_version="v1")["code"], "INTERNAL")

    def test_missing_real_backend_and_fixture_do_not_fallback(self):
        with patch.object(server, "MODE", "real"), patch("server.importlib.import_module", side_effect=ModuleNotFoundError("core.api")), self.assertLogs("fundtrace", level="ERROR"):
            self.assertEqual(server._call("get_account", acct_id="A0087")["code"], "INTERNAL")
        with patch.object(server, "FIXTURES", self.root / "missing"), self.assertLogs("fundtrace", level="ERROR"):
            self.assertEqual(server._call("get_account", acct_id="A0087")["code"], "INTERNAL")

    def test_hybrid_queries_full_dataset_and_keeps_other_tools_fixture(self):
        with patch.object(server, "MODE", "hybrid"):
            account = server._call("get_account", acct_id="A0044")
            self.assertEqual(account["acct_id"], "A0044")
            self.assertEqual(account["_demo"]["mode"], "synthetic_dataset")
            self.assertEqual(account["_demo"]["dataset_id"], "sim-gen_profile_v1-seed42")
            txs = server._call("get_transactions", acct_id="A0044", start=None, end=None, limit=50)
            self.assertNotIn("error", txs)
            self.assertEqual(txs["_demo"]["mode"], "synthetic_dataset")
            trace = server._call("trace_chain", acct_id="A0087", max_hops=4, rule_version="v1")
            self.assertEqual(trace["_demo"]["mode"], "fixture")
            self.assertEqual(trace["acct_id"], "A0087")

    def test_hybrid_query_error_does_not_fallback_to_fixture(self):
        api = ModuleType("core.api")
        api.get_account = lambda **params: {"error": "missing", "code": "ACCOUNT_NOT_FOUND"}
        with patch.object(server, "MODE", "hybrid"), patch.dict(sys.modules, {"core.api": api}), patch.object(server, "_fixture", side_effect=AssertionError("must not fall back")):
            result = server._call("get_account", acct_id="A9999")
        self.assertEqual(result["code"], "ACCOUNT_NOT_FOUND")

    def test_real_algorithm_ticket_roundtrip_and_rejudge(self):
        with patch.object(server, "MODE", "real"), patch.dict(os.environ, {"FUNDTRACE_TICKET_DIR": str(self.root / "tickets")}), patch.object(server, "_fixture", side_effect=AssertionError("no fixtures")):
            for version in ("v1", "v2"):
                ticket = server._call("make_ticket", acct_id="A0176", rule_version=version)
                self.assertNotIn("error", ticket)
                self.assertEqual(ticket["_demo"]["backend_mode"], "real")
                self.assertEqual(server._call("get_ticket", acct_id="A0176", rule_version=version), ticket)
                path = self.root / "tickets" / version / "A0176.json"
                self.assertNotIn("_demo", json.loads(path.read_text(encoding="utf-8")))
            result = server._call("rejudge", old="v1", new="v2")
            self.assertEqual(result["summary"]["total"], 300)
            self.assertEqual(result["summary"]["changed"], len(result["changed"]))
            for name in ("get_account", "trace_chain", "check_rules", "make_ticket", "get_ticket"):
                params = {"acct_id": "A9999"}
                if name != "get_account":
                    params["rule_version"] = "v1"
                if name == "trace_chain":
                    params["max_hops"] = 4
                self.assertEqual(server._call(name, **params)["code"], "ACCOUNT_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
