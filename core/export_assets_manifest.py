"""资产登记表：把数据、规则、知识库文件、案例、本体登记到 eval/assets_manifest.csv。

用法（仓库根目录）：
  python -m core.export_assets_manifest

列：asset_id, asset_type, title, source, version, sha256, is_synthetic
- 数据文件的 sha256 直接取 data/dataset_meta.json；其余文件计算 sha256。
- 文本文件计算前统一把 CRLF 换成 LF，避免 Windows 与 Linux 检出后哈希不同。
- 不写生成时间，重复运行结果完全一致。
- 案例是公开报道摘要（is_synthetic=否），来源链接与访问日期取自案例文件的“来源”行。
只读仓库文件，不读答案目录。
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

from .ruleset import ROOT

OUT = ROOT / "eval" / "assets_manifest.csv"
COLS = ["asset_id", "asset_type", "title", "source", "version", "sha256", "is_synthetic"]
SRC_RE = re.compile(r"^- 来源：\[([^\]]+)\]\(([^)]+)\)")
DATE_RE = re.compile(r"访问日期\s*(\d{4}-\d{2}-\d{2})")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def build_rows() -> list[dict]:
    meta = json.loads((ROOT / "data" / "dataset_meta.json").read_text(encoding="utf-8"))
    ds = meta["dataset_id"]
    rows = []
    for i, name in enumerate(("accounts.csv", "transactions.csv"), 1):
        rows.append({"asset_id": f"D{i:02d}", "asset_type": "数据", "title": f"仿真{('账户表' if i == 1 else '交易表')}（{name}）",
                     "source": f"core/gen_data.py 生成，数据集 {ds}", "version": meta["spec_version"],
                     "sha256": meta["sha256"][name], "is_synthetic": "是"})
    for i, v in enumerate(("v1", "v2"), 1):
        p = ROOT / "Data and Rules" / "rules" / f"rules_{v}.yaml"
        rows.append({"asset_id": f"R{i:02d}", "asset_type": "规则", "title": f"规则集 {v}（仿真内部规则）",
                     "source": _rel(p), "version": v, "sha256": _sha(p), "is_synthetic": "是"})
    for i, (name, v, t) in enumerate((("rules_v1.md", "v1", "规则说明文档 v1"), ("rules_v2.md", "v2", "规则说明文档 v2"),
                                      ("rules_diff_v1_v2.md", "v1→v2", "规则差异说明 v1→v2")), 1):
        p = ROOT / "kb" / name
        rows.append({"asset_id": f"K{i:02d}", "asset_type": "知识库文档", "title": f"{t}（由 core/export_rules_md.py 生成）",
                     "source": _rel(p), "version": v, "sha256": _sha(p), "is_synthetic": "是"})
    for i, p in enumerate(sorted((ROOT / "kb" / "cases").glob("case*.md")), 1):
        text = p.read_text(encoding="utf-8")
        title, url, date = p.stem, "", ""
        for line in text.splitlines():
            m = SRC_RE.match(line)
            if m:
                title, url = m.group(1), m.group(2)
                d = DATE_RE.search(line)
                date = d.group(1) if d else ""
                break
        rows.append({"asset_id": f"C{i:02d}", "asset_type": "案例", "title": f"{title}（摘要为本作品改写）",
                     "source": url or _rel(p), "version": f"访问日期 {date}" if date else "—",
                     "sha256": _sha(p), "is_synthetic": "否"})
    p = ROOT / "ontology" / "tbox_v1.yaml"
    rows.append({"asset_id": "O01", "asset_type": "本体", "title": "领域本体 TBox v1",
                 "source": _rel(p), "version": "v1", "sha256": _sha(p), "is_synthetic": "是"})
    return rows


def main() -> int:
    rows = build_rows()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"已写入 {OUT}（{len(rows)} 条）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
