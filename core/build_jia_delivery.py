"""Build reproducible code/data and presentation-source handoff archives."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
FOLDERS = ("Data and Rules", "data", "core", "tickets", "eval", "ontology", "tests",
           "mcp_server", "kb", "agent")
EXCLUDED = {"__pycache__", ".pytest_cache", ".venv", "dist", ".git", ".playwright-mcp"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_files():
    paths = [ROOT / "README.md", ROOT / "requirements.txt"]
    for folder in FOLDERS:
        paths.extend(p for p in (ROOT / folder).rglob("*") if p.is_file()
                     and not any(x in EXCLUDED or x.startswith("_tmp") for x in p.relative_to(ROOT).parts)
                     and p.suffix not in {".pyc", ".bak", ".log"})
    return sorted(set(paths))


def audit_module():
    spec = importlib.util.spec_from_file_location("handoff_scan", ROOT / "agent/handoff/build_delivery.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_archive(name: str, content: dict[str, bytes], scanner) -> dict:
    for path, data in content.items():
        scanner.safe_path(path)
        scanner.scan(path, data)
    manifest = {"scope": "Internal handoff; synthetic data; external media acceptance separate",
                "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "working_tree_overlay": True,
                "hash_policy": "Packaged bytes; text normalized to LF",
                "files": [{"path": p, "size": len(b), "sha256": digest(b)} for p, b in sorted(content.items())]}
    content = dict(content)
    content["MANIFEST.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = DIST / (name + ".zip")
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, data in sorted(content.items()):
            item = zipfile.ZipInfo(path, (2026, 10, 31, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = (0o100755 if path.endswith(".sh") else 0o100644) << 16
            archive.writestr(item, data)
    with tempfile.TemporaryDirectory(prefix="fundtrace-jia-") as directory:
        base = Path(directory)
        with zipfile.ZipFile(target) as archive:
            if archive.testzip() is not None or set(archive.namelist()) != set(content):
                raise ValueError("Archive contents/CRC mismatch")
            for item in archive.infolist():
                scanner.safe_path(item.filename)
            archive.extractall(base)
        for item in manifest["files"]:
            if digest((base / item["path"]).read_bytes()) != item["sha256"]:
                raise ValueError("Extracted hash mismatch: " + item["path"])
        if "data/dataset_meta.json" in content:
            meta = json.loads(content["data/dataset_meta.json"])
            for path, expected in meta["sha256"].items():
                if digest(content["data/" + path]) != expected:
                    raise ValueError("Frozen data mismatch: " + path)
        for path, data in content.items():
            if path.endswith(".py"):
                compile(data, path, "exec")
    result = {"archive": target.name, "sha256": digest(target.read_bytes()),
              "files": len(content), "crc_extraction_hashes": "PASS", "credential_patterns": "NO_MATCH",
              "frozen_data": "PASS" if "data/dataset_meta.json" in content else "NOT_INCLUDED"}
    target.with_suffix(".sha256").write_text(result["sha256"] + "  " + target.name + "\n", encoding="ascii")
    target.with_suffix(".verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    DIST.mkdir(exist_ok=True)
    scanner = audit_module()
    text_extensions = {".py", ".md", ".csv", ".json", ".yaml", ".yml", ".txt", ".sh", ".ps1"}
    content = {}
    for path in source_files():
        data = path.read_bytes()
        if path.suffix in text_extensions:
            data = data.replace(b"\r\n", b"\n")
        content[path.relative_to(ROOT).as_posix()] = data
    full = write_archive("fundtrace-jia-code-data-20261031", content, scanner)
    prefixes = ("eval/", "ontology/", "kb/", "data/README.md", "agent/handoff/DEMO.md",
                "agent/handoff/丙_校赛PPT制作说明.md")
    materials = {p: b for p, b in content.items() if p.startswith(prefixes)
                 and p not in {"eval/answer.csv", "eval/answer_tx.csv"}}
    materials["README.md"] = content["eval/handoff/README.md"]
    handoff = write_archive("fundtrace-bing-materials-20261031", materials, scanner)
    print(json.dumps([full, handoff], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
