"""Split a final-answer-only browser regression export into auditable artifacts."""

import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path)
    args = parser.parse_args()
    data = json.loads(args.export.read_text(encoding="utf-8"))
    root = args.export.parent
    records = []
    for item in data["results"]:
        stem = item["id"] if item["kind"] == "extract" else f'{item["id"]}-{item["kind"]}'
        answer = item.get("final", "")
        (root / f"{stem}-answer.md").write_text(answer, encoding="utf-8")
        record = {k: item.get(k) for k in ("id", "kind", "query", "status", "finished", "error")}
        digest = hashlib.sha256(answer.encode("utf-8")).hexdigest()
        record["sha256"] = ":".join(digest[i:i + 8] for i in range(0, 64, 8))
        if item["kind"] == "extract":
            try:
                json.loads(answer)
            except ValueError:
                record["json_parse"] = False
            else:
                record["json_parse"] = True
                (root / f'{item["id"]}.json').write_text(answer, encoding="utf-8")
        records.append(record)
    (root / "manifest.json").write_text(
        json.dumps({"started": data.get("started"), "running": data.get("running"),
                    "count": len(records), "records": records}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Archived {len(records)} final answers; original response text preserved.")


if __name__ == "__main__":
    main()
