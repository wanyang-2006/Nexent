"""生成带文本层的工单 PDF（matplotlib，嵌入微软雅黑），用于对比 analyze_text_file 对文本 PDF 与图片 PDF 的处理。

用法（仓库根目录）：python multimodal/gen_m0_textpdf.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.backends.backend_pdf import PdfPages

ROOT = Path(__file__).resolve().parent.parent
font_manager.fontManager.addfont("C:/Windows/Fonts/msyh.ttc")
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
plt.rcParams["pdf.fonttype"] = 42

t = json.loads((ROOT / "tickets" / "v1" / "A0209.json").read_text(encoding="utf-8"))
lines = ["涉诈资金链路研判工单（仿真数据）", ""]
for k in ("ticket_id", "acct_id", "rule_version", "status", "role", "chain_id", "conclusion"):
    if k in t:
        lines.append(f"{k}: {t[k]}")
for k in ("supporting_evidence", "counter_evidence", "missing_evidence", "rule_basis", "suggested_actions"):
    v = t.get(k)
    if v is None:
        continue
    lines.append(f"{k}:")
    for item in (v if isinstance(v, list) else [v]):
        s = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
        while s:
            lines.append("    " + s[:60]); s = s[60:]
out = ROOT / "multimodal" / "samples" / "m0_ticket_A0209_text.pdf"
with PdfPages(out) as pdf:
    for start in range(0, len(lines), 48):
        fig = plt.figure(figsize=(8.27, 11.69))
        for i, line in enumerate(lines[start:start + 48]):
            fig.text(0.06, 0.95 - i * 0.019, line, fontsize=9)
        pdf.savefig(fig); plt.close(fig)
print(out)
