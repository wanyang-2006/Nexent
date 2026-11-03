"""由 kb/sources/fzf_law_full.txt 生成法规库语料（kb/chunks/laws/），逐字取自法律原文。

用法（仓库根目录）：python kb/build_law_chunks.py
不含任何仿真规则、账户号或交易号。
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "chunks" / "laws"
ARTS = {15: "金融治理：客户尽职调查", 16: "金融治理：开户数量与异常开户", 17: "金融治理：企业账户异常开户",
        18: "金融治理：异常账户与可疑交易监测", 19: "金融治理：交易信息完整传输", 20: "金融治理：涉案资金查询止付冻结",
        31: "账户买卖、出租、出借的禁止", 38: "参与、帮助诈骗的法律责任", 40: "银行、支付机构未履行义务的法律责任",
        44: "违反第三十一条第一款的法律责任"}
CN = "零一二三四五六七八九"


def cn(n: int) -> str:
    if n < 10:
        return CN[n]
    t, o = divmod(n, 10)
    return ("" if t == 1 else CN[t]) + "十" + (CN[o] if o else "")


def main() -> int:
    lines = [l.strip() for l in (HERE / "sources" / "fzf_law_full.txt").read_text(encoding="utf-8").split("\n") if l.strip()]
    start = {}
    for i, l in enumerate(lines):
        m = re.match(r"^第([一二三四五六七八九十]+)条\s", l)
        if m:
            start[m.group(1)] = i
    heads = sorted(start.values())
    chapter = [i for i, l in enumerate(lines) if re.match(r"^第[一二三四五六七八九十]+章", l)]
    stops = sorted(set(heads + chapter + [len(lines)]))
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.md"):
        old.unlink()
    for n, title in ARTS.items():
        i = start[cn(n)]
        j = next(s for s in stops if s > i)
        body = "\n\n".join(lines[i:j])
        text = f"""# 法规原文｜反电信网络诈骗法｜第{cn(n)}条｜{title}

- 法规：《中华人民共和国反电信网络诈骗法》（2022 年 9 月 2 日通过，2022 年 12 月 1 日起施行）
- 条号：第{cn(n)}条
- 来源：https://amr.hunan.gov.cn/amr/zwx/xxgkmlx/zcfgx/zcfgxx/202304/t20230407_29307827.html
- 访问日期：2026-11-02
- 核对状态：正文逐字取自上述公开页面，未改写；官方文本以全国人大网发布的为准

## 原文

{body}

使用说明：以上为法律原文。引用时写明法规名称和条号；认定权在公安机关和司法机关。
"""
        (OUT / f"law_fzf_{n:03d}.md").write_text(text, encoding="utf-8", newline="\n")
    print(f"已生成 {len(ARTS)} 个文件到 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
