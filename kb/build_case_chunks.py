"""由 kb/sources/ 中最高检、“两高一部”发布的典型案例原文生成补充案例语料（kb/chunks/cases_real/）。

一个案例一个文件，正文逐字取自公开页面（基本案情、典型意义、检察官提醒），不含仿真规则。
用法（仓库根目录）：python kb/build_case_chunks.py
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "chunks" / "cases_real"
ACCESS = "2026-11-05"
SRC = {
    "spp2023": ("检察机关依法惩治电信网络诈骗及其关联犯罪典型案例（最高人民检察院，2023-11-30）",
                "https://www.spp.gov.cn/xwfbh/dxal/202311/t20231130_635225.shtml",
                "spp2023_telecom_fraud_cases.txt"),
    "spp2025": ("依法惩治帮助信息网络犯罪活动及相关犯罪典型案例（最高人民法院、最高人民检察院、公安部，2025-07-28）",
                "https://www.spp.gov.cn/xwfbh/wsfbt/202507/t20250728_702377.shtml",
                "spp2025_bangxin_cases.txt"),
}
# 文件名、来源、案例序号、手法标签（本知识库的分类，便于检索）
PICK = [
    ("case06_冒充公司负责人诱骗财务转账", "spp2023", "案例一", "冒充领导熟人；对公账户大额转账"),
    ("case07_虚拟投资平台诱导交易", "spp2023", "案例四", "虚假网络投资理财"),
    ("case08_AI语音机器人推送虚假贷款", "spp2023", "案例六", "虚假网络贷款；掩饰、隐瞒犯罪所得"),
    ("case09_跑分团伙为电诈洗钱", "spp2023", "案例七", "跑分洗钱；资金分层转移"),
    ("case10_以投资虚拟币为幌子诈骗", "spp2023", "案例八", "虚假网络投资理财；虚拟币"),
    ("case11_出借银行卡的轻微不法行为", "spp2023", "案例九", "出租出借银行卡；掩饰、隐瞒犯罪所得"),
    ("case12_出售空壳公司营业执照和对公账户", "spp2023", "案例十一", "买卖对公账户；空壳公司"),
    ("case13_与诈骗团伙通谋转移资金", "spp2025", "案例五", "取现转账配合；诈骗共犯"),
    ("case14_两卡犯罪综合认定", "spp2025", "案例六", "出售出租银行卡；掩饰、隐瞒犯罪所得"),
    ("case15_在校学生帮助信息网络犯罪活动", "spp2025", "案例七", "在校学生出借银行卡；帮助信息网络犯罪活动"),
]
KEEP = {"【基本案情】", "【典型意义】", "【检察官提醒】"}


def case_block(lines, label):
    heads = [i for i, l in enumerate(lines) if re.fullmatch(r"案例[一二三四五六七八九十]+", l)]
    i = next(k for k in heads if lines[k] == label)
    j = next((k for k in heads if k > i), len(lines))
    end = next((k for k in range(i, j) if lines[k].startswith("检察日报") or lines[k].startswith("（来源")), j)
    blk = lines[i + 1:end]
    title, sub = blk[0], blk[1] if len(blk) > 1 and blk[1].startswith("——") else ""
    out, keep = [], False
    for l in blk[2 if sub else 1:]:
        if l.startswith("【"):
            keep = l in KEEP
            if keep:
                out += ["", "## " + l.strip("【】"), ""]
            continue
        if keep:
            out.append(l)
    return title, sub, out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.md"):
        old.unlink()
    for fname, src, label, tag in PICK:
        name, url, txt = SRC[src]
        lines = [l.strip() for l in (HERE / "sources" / txt).read_text(encoding="utf-8").split("\n") if l.strip()]
        title, sub, body = case_block(lines, label)
        text = [f"# 真实案例｜{title}", "", f"- 手法：{tag}｜类型：司法机关发布的典型案例",
                f"- 出处：{name}，{label}", f"- 来源：{url}", f"- 访问日期：{ACCESS}",
                "- 核对状态：正文逐字取自上述公开页面，未改写；“检察履职/诉讼过程”部分未收录", ""]
        if sub:
            text.append(sub)
        text += body
        text += ["", "使用说明：以上为公开典型案例原文，当事人已由原发布机关匿名化。用于说明手法和资金特征，不能作为任何具体账户的证据。"]
        (OUT / f"{fname}.md").write_text("\n".join(text) + "\n", encoding="utf-8", newline="\n")
    print(f"已生成 {len(PICK)} 个文件到 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
