"""比对视觉模型的字段识别结果与标准答案（方案第 8 节指标）。

用法（仓库根目录）：python multimodal/score.py multimodal/results/m2_extract.json
结果文件格式：{"transfer_01": {模型输出的 JSON 字段...}, ...}，键为素材文件名（不含扩展名）。
模型输出使用 4.2 节的英文字段名；缺失字段视为 null。
指标：按字段统计准确率；amount、time、payee_type 单独报告；模糊/遮挡图检查“不可读字段”是否如实标注。
"""
import json
import re
import sys
from pathlib import Path

SET = Path(__file__).resolve().parent / "samples" / "set1"
FIELDS = ["payee_name", "payee_account_tail", "payee_type", "amount", "time", "channel", "remark"]


def norm(field, v):
    if v in (None, "", "null", "无", "未显示"):
        return None
    if field == "amount":
        try:
            return round(float(str(v).replace(",", "").replace("¥", "").replace("元", "").replace("CNY", "").strip()), 2)
        except ValueError:
            return str(v)
    s = re.sub(r"\s+", "", str(v))
    if field == "time":
        m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})日?(\d{1,2}):(\d{2})", s)
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d} {int(m.group(4)):02d}:{m.group(5)}" if m else s
    if field == "payee_account_tail":
        m = re.findall(r"\d{4}", s)
        return m[-1] if m else s
    return s


def match(field, got, exp):
    g, e = norm(field, got), norm(field, exp)
    if field == "channel" and g and e:
        return e in g or g in e
    return g == e


def main(path):
    sys.stdout.reconfigure(encoding="utf-8")
    res = json.loads(Path(path).read_text(encoding="utf-8"))
    per = {f: [0, 0] for f in FIELDS}
    rows, unread = [], []
    for name, got in sorted(res.items()):
        tp = SET / f"{name}.json"
        if not tp.exists():
            continue
        truth = json.loads(tp.read_text(encoding="utf-8"))
        if "payee_name" not in truth:
            continue
        miss = []
        for fld in FIELDS:
            if fld in truth.get("expect_unreadable", []):
                continue
            per[fld][1] += 1
            if match(fld, got.get(fld), truth.get(fld)):
                per[fld][0] += 1
            else:
                miss.append(f"{fld}: 识别={got.get(fld)!r} 真值={truth.get(fld)!r}")
        for fld in truth.get("expect_unreadable", []):
            ok = norm(fld, got.get(fld)) is None or fld in (got.get("unreadable_fields") or [])
            unread.append((name, fld, ok, got.get(fld)))
        rows.append((name, miss))
    tot = [sum(v[0] for v in per.values()), sum(v[1] for v in per.values())]
    print(f"素材 {len(rows)} 份，字段总准确率 {tot[0]}/{tot[1]} = {tot[0] / max(tot[1], 1):.1%}")
    for fld, (a, n) in per.items():
        print(f"  {fld:<20} {a}/{n}")
    for name, miss in rows:
        for m in miss:
            print(f"  XX {name} {m}")
    for name, fld, ok, v in unread:
        print(f"  {'OK' if ok else 'XX'} 不可读标注 {name}.{fld}（识别值 {v!r}）")


if __name__ == "__main__":
    main(sys.argv[1])
