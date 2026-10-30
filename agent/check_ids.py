"""Check identifiers in an answer against local synthetic data and chain APIs."""

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import api
from core.store import get_store


def extract_ids(text):
    patterns = yaml.safe_load(
        (ROOT / "Data and Rules" / "enums.yaml").read_text(encoding="utf-8-sig")
    )["id_patterns"]

    def find(key, content):
        pattern = patterns[key].removeprefix("^").removesuffix("$")
        return sorted(set(re.findall(
            rf"(?<![A-Za-z0-9])(?:{pattern})(?![A-Za-z0-9])", content
        )))

    chains = find("system_chain_id", text)
    # A chain's seed is not a separately cited transaction.
    without_chains = text
    for chain in sorted(chains, key=len, reverse=True):
        without_chains = without_chains.replace(chain, " " * len(chain))
    return {
        "accounts": find("acct_id", text),
        "transactions": find("tx_id", without_chains),
        "chains": chains,
    }


def check_text(text, rule_version="v1"):
    identifiers = extract_ids(text)
    store = get_store()
    known = {"accounts": set(store.accounts), "transactions": set(store.tx_by_id)}
    known["chains"] = set()
    if identifiers["chains"]:
        # Query all accounts so chain validation is independent of answer wording.
        for acct_id in store.accounts:
            result = api.trace_chain(acct_id, rule_version=rule_version)
            if "error" in result:
                raise ValueError(f"trace_chain failed: {result['error']}")
            known["chains"].update(c["chain_id"] for c in result["chains"])
    unknown = {
        kind: [value for value in values if value not in known[kind]]
        for kind, values in identifiers.items()
    }
    has_ids = any(identifiers.values())
    return {
        "rule_version": rule_version,
        "dataset_id": store.dataset_id,
        "identifiers": identifiers,
        "unknown": unknown,
        "status": "NO_IDS" if not has_ids else "FAIL" if any(unknown.values()) else "PASS",
    }


def final_answer_from_sse(text):
    answers = []
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        event = json.loads(payload)
        if event.get("type") == "final_answer":
            content = event.get("content")
            if not isinstance(content, str):
                raise ValueError("final_answer.content must be text")
            answers.append(content)
    if not answers:
        raise ValueError("SSE contains no final_answer event")
    return "\n\n".join(answers)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("answer", nargs="?", help="UTF-8 answer file; omit or use - for stdin")
    parser.add_argument("--rule-version", choices=("v1", "v2"), default="v1")
    parser.add_argument("--sse-final", action="store_true", help="Read only final_answer SSE events")
    parser.add_argument("--json", action="store_true", help="Print a structured report")
    args = parser.parse_args(argv)
    try:
        text = (Path(args.answer).read_text(encoding="utf-8-sig")
                if args.answer and args.answer != "-" else sys.stdin.read().lstrip("\ufeff"))
        if args.sse_final:
            text = final_answer_from_sse(text)
        result = check_text(text, args.rule_version)
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{result['status']}: dataset={result['dataset_id']}; rules={args.rule_version}")
        for kind, values in result["identifiers"].items():
            print(f"{kind}: {len(values)}; unknown={result['unknown'][kind]}")
        print("Identifier existence only; amounts, relationships and completeness are not checked.")
    return {"PASS": 0, "FAIL": 1, "NO_IDS": 2}[result["status"]]


if __name__ == "__main__":
    sys.exit(main())
