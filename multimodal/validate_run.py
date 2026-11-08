"""Validate saved extraction outputs against the receipt JSON Schema."""

import argparse
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--schema", type=Path, default=Path(__file__).parent / "schemas" / "receipt.schema.json")
    parser.add_argument("--semantics", action="store_true", help="Also check sample names, explicit account types and visibility classification")
    args = parser.parse_args()
    schema_path = args.schema
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    sample_dir = Path(__file__).parent / "samples" / "set1"
    sample_ids = json.loads((sample_dir / "ids.json").read_text(encoding="utf-8"))
    reports = []
    for path in sorted(args.run_dir.glob("*.json")):
        if not re.fullmatch(r"[RBCUX]\d{2}(?:-risk-extract\d*)?", path.stem):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            errors = [
                {"path": list(error.absolute_path), "message": error.message}
                for error in sorted(validator.iter_errors(data), key=lambda e: str(list(e.absolute_path)))
            ]
            if args.semantics and not errors:
                sid = path.stem.split("-")[0]
                truth = json.loads((sample_dir / Path(sample_ids[sid]).with_suffix(".json")).read_text(encoding="utf-8"))
                for field in ("payee_name", "payee_type"):
                    if sid.startswith(("R", "B", "U", "X")) and data.get(field) != truth.get(field):
                        errors.append({"path": [field], "message": "Value differs from the sample truth; do not repair the saved output"})
                not_shown = set(data.get("not_shown_fields") or [])
                unreadable = set(data.get("unreadable_fields") or [])
                if not_shown & unreadable:
                    errors.append({"path": [], "message": "not_shown_fields and unreadable_fields overlap"})
                for field in truth.get("expect_unreadable", []):
                    if field not in unreadable or field in not_shown:
                        errors.append({"path": [field], "message": "Occluded field must be classified as unreadable"})
                for field in ("payer_bank", "payee_bank"):
                    if data.get(field) in {"储蓄卡", "借记卡", "信用卡"}:
                        errors.append({"path": [field], "message": "Card type is not a bank"})
        except (ValueError, OSError) as error:
            errors = [{"path": [], "message": str(error)}]
        reports.append({"file": path.name, "passed": not errors, "errors": errors})
    result = {"total": len(reports), "passed": sum(r["passed"] for r in reports), "results": reports}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if reports and all(r["passed"] for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
