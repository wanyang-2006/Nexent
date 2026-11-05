"""多模态交付物自检（任务分工 J6 依据核对 + J8 安全自检）。

用法（仓库根目录）：python multimodal/selfcheck.py
检查：
  1. risk_signals.md 每行引用的知识库文件都存在，「」内的原文片段逐字出现在该行引用的文件中
  2. multimodal/、kb/chunks/scams/ 下的文本文件中没有疑似真实个人信息或密钥：
     手机号、身份证号、完整银行卡号（13 位以上连续数字）、邮箱、API Key / Bearer Token
任何一项不通过时退出码为 1。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = [ROOT / "multimodal", ROOT / "kb" / "chunks" / "scams"]
TEXT_EXT = {".py", ".md", ".json", ".csv", ".txt", ".js"}
PATTERNS = {
    "手机号": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "身份证号": re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
    "银行卡号": re.compile(r"(?<!\d)\d{13,19}(?!\d)"),
    "邮箱": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "API Key": re.compile(r"\bsk-[A-Za-z0-9]{16,}|Bearer\s+[A-Za-z0-9._-]{16,}|(?i:api[_-]?key)\s*[:=]\s*['\"][^'\"]{8,}"),
}


def squash(s):
    return re.sub(r"\s+", "", s)


def check_citations():
    errs, n = [], 0
    for line in (ROOT / "multimodal" / "risk_signals.md").read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        files = [ROOT / p for p in re.findall(r"`(kb/chunks/[^`]+\.md)`", line)]
        quotes = re.findall(r"「([^」]+)」", line)
        if not files:
            continue
        missing = [str(f.relative_to(ROOT)) for f in files if not f.exists()]
        if missing:
            errs.append(f"文件不存在：{missing}")
            continue
        text = squash("".join(f.read_text(encoding="utf-8") for f in files))
        for q in quotes:
            n += 1
            if squash(q) not in text:
                errs.append(f"原文未找到：「{q}」 in {[f.name for f in files]}")
    return n, errs


def scan():
    hits = []
    for d in SCAN_DIRS:
        for f in sorted(d.rglob("*")):
            if f.suffix not in TEXT_EXT or not f.is_file():
                continue
            for k, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                for name, pat in PATTERNS.items():
                    for m in pat.finditer(line):
                        hits.append(f"{f.relative_to(ROOT)}:{k} {name} {m.group(0)[:40]}")
    return hits


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    n, errs = check_citations()
    print(f"[依据核对] risk_signals.md 原文片段 {n} 条，未通过 {len(errs)} 条")
    for e in errs:
        print("  XX", e)
    hits = scan()
    print(f"[敏感信息] 扫描 {', '.join(str(d.relative_to(ROOT)) for d in SCAN_DIRS)}，疑似 {len(hits)} 处")
    for h in hits:
        print("  XX", h)
    sys.exit(1 if errs or hits else 0)


if __name__ == "__main__":
    main()
