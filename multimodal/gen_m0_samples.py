"""生成 M0 平台能力核实用的两份虚构样例：一张转账成功截图、一份工单 PDF。

用法（仓库根目录）：python multimodal/gen_m0_samples.py
所有姓名、账号均为虚构；工单 PDF 由 tickets/v1/A0209.json 渲染。
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "multimodal" / "samples"
FONT = "C:/Windows/Fonts/msyh.ttc"
BOLD = "C:/Windows/Fonts/msyhbd.ttc"


def f(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)


def transfer_screenshot() -> dict:
    truth = {
        "doc_type": "转账成功页", "payer_name": "张*明", "payer_account_tail": "3821", "payer_bank": "示例银行",
        "payee_name": "李*华", "payee_account_tail": "6607", "payee_bank": "演示农商银行", "payee_type": None,
        "amount": 38000.00, "currency": "CNY", "time": "2026-11-04 21:47", "channel": "手机银行",
        "remark": "安全账户资金核验", "serial_no_tail": "5932",
    }
    W, H = 750, 1334
    im = Image.new("RGB", (W, H), "#F4F6FA")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 120], fill="#C8102E")
    d.text((W // 2, 75), "示例银行 手机银行", font=f(34, True), fill="white", anchor="mm")
    d.ellipse([W // 2 - 60, 180, W // 2 + 60, 300], fill="#2BB673")
    d.line([(W // 2 - 30, 240), (W // 2 - 8, 262), (W // 2 + 32, 218)], fill="white", width=10)
    d.text((W // 2, 350), "转账成功", font=f(44, True), fill="#222", anchor="mm")
    d.text((W // 2, 430), "¥ 38,000.00", font=f(56, True), fill="#111", anchor="mm")
    rows = [("收款人", "李*华"), ("收款账户", "演示农商银行 (6607)"), ("付款账户", "示例银行储蓄卡 (3821)"),
            ("付款人", "张*明"), ("转账时间", "2026-11-04 21:47:12"), ("转账方式", "实时到账"),
            ("用途/附言", "安全账户资金核验"), ("交易流水号", "**** **** 5932")]
    y = 540
    d.rounded_rectangle([30, 500, W - 30, 500 + 80 * len(rows) + 40], radius=20, fill="white")
    for k, v in rows:
        d.text((70, y), k, font=f(30), fill="#888")
        d.text((W - 70, y), v, font=f(30), fill="#222", anchor="ra")
        y += 80
    d.text((W // 2, H - 80), "样例图片：信息均为虚构，仅用于测试", font=f(24), fill="#AAA", anchor="mm")
    im.save(OUT / "m0_transfer_01.png")
    (OUT / "m0_transfer_01.json").write_text(json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8")
    return truth


def ticket_pdf():
    t = json.loads((ROOT / "tickets" / "v1" / "A0209.json").read_text(encoding="utf-8"))
    W, H = 1240, 1754
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    d.text((80, 80), "涉诈资金链路研判工单（仿真数据）", font=f(44, True), fill="black")
    y = 180
    lines = []
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
                lines.append("    " + s[:52])
                s = s[52:]
    for line in lines:
        if y > H - 120:
            break
        d.text((80, y), line, font=f(26), fill="black")
        y += 44
    d.text((80, H - 80), "由 tickets/v1/A0209.json 渲染，仅用于测试", font=f(22), fill="#888")
    im.save(OUT / "m0_ticket_A0209.pdf", "PDF", resolution=150)
    return t.get("ticket_id")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    transfer_screenshot()
    print("ticket", ticket_pdf())
    print("done", sorted(p.name for p in OUT.iterdir()))
