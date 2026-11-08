"""把本系统工单 JSON 渲染为带文字层的 PDF（任务分工 J3，方案 5.5 / M5 测试素材）。

用法（仓库根目录）：python multimodal/render_ticket_pdf.py [--out 目录]
输入：tickets/<版本>/<账户号>.json（程序生成的演示工单，仿真数据）
输出（默认 multimodal/samples/set1/）：
  P01 ticket_A0209_v1.pdf           原样渲染，期望核验“一致”
  P02 ticket_A0105_v1.pdf           原样渲染，期望“一致”
  P03 ticket_A0176_v2.pdf           原样渲染，期望“一致”
  P04 ticket_A0044_v1.pdf           状态由“存在风险信号”改为“未见异常”，期望“不一致”，差异字段 status
  文件名不带“篡改”字样：平台实测模型会把文件名当作线索（2026-11-05 用旧名 *_tampered.pdf 测试时出现）
  每个 PDF 旁边有同名 .json 标准答案（含 id、expect、diff_fields、被改字段的原值与改后值）。

为什么用 matplotlib 而不是 PIL：PIL 存的 PDF 只有图片，没有文字层；M0 实测纯图片 PDF 会让智能体反复切图，
耗时超过 5 分钟。matplotlib 以 TrueType（fonttype 42）嵌入字体，analyze_text_file 可直接提取文字（约 17 秒）。
PDF 元数据里的创建时间已去掉，同一输入两次生成的文件逐字节相同。
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "multimodal" / "samples" / "set1"
FONT = "C:/Windows/Fonts/msyh.ttc"
TICKET_DIR = ROOT / "tickets"
# 编号, 账户号, 规则版本, 篡改内容（None 为原样）
CASES = [
    ("P01", "A0209", "v1", None),
    ("P02", "A0105", "v1", None),
    ("P03", "A0176", "v2", None),
    ("P04", "A0044", "v1", {"status": "未见异常"}),
]
HEAD_KEYS = ("ticket_id", "acct_id", "rule_version", "status", "role", "chain_id", "conclusion")
LIST_KEYS = ("supporting_evidence", "counter_evidence", "missing_evidence", "rule_basis", "suggested_actions")
LINES_PER_PAGE = 48


def ticket_lines(t):
    lines = ["涉诈资金链路研判工单（仿真数据）", ""]
    for k in HEAD_KEYS:
        if k in t:
            lines.append(f"{k}: {t[k]}")
    for k in LIST_KEYS:
        v = t.get(k)
        if v is None:
            continue
        lines.append(f"{k}:")
        for item in (v if isinstance(v, list) else [v]):
            s = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
            while s:
                lines.append("    " + s[:60])
                s = s[60:]
    return lines


def render(lines, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib.backends.backend_pdf import PdfPages
    font_manager.fontManager.addfont(FONT)
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
    plt.rcParams["pdf.fonttype"] = 42
    with PdfPages(path, metadata={"CreationDate": None, "Producer": None, "Creator": None}) as pdf:
        for start in range(0, len(lines), LINES_PER_PAGE):
            fig = plt.figure(figsize=(8.27, 11.69))
            for k, line in enumerate(lines[start:start + LINES_PER_PAGE]):
                fig.text(0.06, 0.95 - k * 0.019, line, fontsize=9)
            pdf.savefig(fig)
            plt.close(fig)


def build(out=OUT, manifest=None):
    out.mkdir(parents=True, exist_ok=True)
    for sid, acct, ver, tamper in CASES:
        t = json.loads((TICKET_DIR / ver / f"{acct}.json").read_text(encoding="utf-8"))
        name = f"ticket_{acct}_{ver}"
        render(ticket_lines(dict(t, **(tamper or {}))), out / f"{name}.pdf")
        truth = {"id": sid, "kind": "ticket", "acct_id": acct, "rule_version": ver, "ticket_id": t.get("ticket_id"),
                 "expect": "不一致" if tamper else "一致",
                 "diff_fields": sorted(tamper) if tamper else [],
                 "tampered": {k: {"system": t.get(k), "pdf": v} for k, v in (tamper or {}).items()},
                 "system_status": t.get("status")}
        (out / f"{name}.json").write_text(json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8")
        if manifest is not None:
            manifest.append({"id": sid, "file": f"{name}.pdf", "kind": "ticket"})
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    print(f"工单 PDF {len(CASES)} 份 -> {build(a.out)}")
