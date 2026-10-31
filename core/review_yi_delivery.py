"""Independently recount archived V9 runs and validate identifiers by rule version."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent.check_ids import check_text  # noqa: E402


def review() -> list[dict]:
    folder = ROOT / "agent/evaluations/regression"
    reports = []
    for name in ("three-skills-release-20261031-checks.json",
                 "three-skills-v9-published-20261031-checks.json",
                 "v9-restore-20261031-checks.json"):
        record = json.loads((folder / name).read_text(encoding="utf-8-sig"))
        runs, problems, call_count = record["runs"], [], 0
        for index, run in enumerate(runs, 1):
            answer = run.get("final_answer", "")
            reports_by_version = [check_text(answer, version) for version in ("v1", "v2")]
            # A comparison can mention chains from both versions. Unknown must fail both.
            unknown = {kind: sorted(set(reports_by_version[0]["unknown"][kind]) &
                                    set(reports_by_version[1]["unknown"][kind]))
                       for kind in ("accounts", "transactions", "chains")}
            # Explicit nonexistent-account tests are expected to name A9999.
            if "ACCOUNT_NOT_FOUND" in answer:
                unknown["accounts"] = [a for a in unknown["accounts"] if a != "A9999"]
            if any(unknown.values()):
                problems.append({"run": index, "unknown": unknown})
            checks = run.get("tool_checks", run.get("business_checks", []))
            call_count += len(checks)
            if any(check.get("matches_local") is not True for check in checks):
                problems.append({"run": index, "stored_business_check": "FAIL"})
            if not answer:
                problems.append({"run": index, "final_answer": "MISSING"})
        reports.append({"file": name, "runs": len(runs), "business_checks": call_count,
                        "independent_id_problems": problems,
                        "scope": "IDs recomputed locally; stored business equality flags recounted, not raw SSE replay"})
    return reports


if __name__ == "__main__":
    result = review()
    output = ROOT / "_tmp_checks/yi-independent-review.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(1 if any(x["independent_id_problems"] for x in result) else 0)
