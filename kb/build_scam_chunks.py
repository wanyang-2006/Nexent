"""由 kb/sources/ 中公安部公布的高发电诈类型原文生成“防骗话术库”语料（kb/chunks/scams/）。

正文逐字取自公开页面，一个诈骗类型一个文件；不含账户号、交易号和仿真规则。
用法（仓库根目录）：python kb/build_scam_chunks.py
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "chunks" / "scams"
ACCESS = "2026-11-05"
SRC24 = ("公安部公布十大高发电信网络诈骗类型（2024 年发布，新疆塔城地区行政公署转载）",
         "https://www.xjtc.gov.cn/zfxxgk/xxgkzl/tcdqhsjg/tcdqhzgszzjg1/gaj/gksx7/jfts/content_3747")
SRC25 = ("小心被骗子盯上！公安部公布高发电诈类型Top 10（2025-07-04，中国驻缅甸使馆网站转载）",
         "https://mm.china-embassy.gov.cn/lsfw/202507/t20250704_11665217.htm")

# 文件名、2024 版标题、2025 版标题（无对应时为 None）、常见关键词（便于检索，取自原文用语）
TYPES = [
    ("01_shuadan", "刷单返利类诈骗", "刷单返利类诈骗", "兼职 刷单 点赞 返佣金 做任务 垫付 组合任务单"),
    ("02_touzi", "虚假网络投资理财类诈骗", "虚假网络投资理财类诈骗", "投资导师 荐股 直播课 高额回报 内幕消息 投资群 提现"),
    ("03_daikuan", "虚假网络贷款类诈骗", "贷款、征信类诈骗", "无抵押 免征信 快速放贷 手续费 保证金 解冻金 会员费"),
    ("04_kefu", "冒充电商物流客服类诈骗", "冒充电商物流客服类诈骗", "客服 退款 理赔 快递丢失 屏幕共享 下载APP 验证码"),
    ("05_gongjianfa", "冒充公检法类诈骗", "冒充公检法类诈骗", "公安 检察院 法院 涉嫌洗钱 通缉令 逮捕证 安全账户 保密"),
    ("06_zhengxin", "虚假征信类诈骗", "贷款、征信类诈骗", "注销校园贷 消除不良记录 影响征信 银保监会 认证账户"),
    ("07_gouwu", "虚假购物、服务类诈骗", "虚假购物、服务类诈骗", "低价 海外代购 私下交易 论文代写 补缴关税 拉黑"),
    ("08_shuren", "冒充领导、熟人类诈骗", "冒充领导、熟人类诈骗", "领导 老师 熟人 工作群 转账 不方便接电话"),
    ("09_youxi", "网络游戏产品虚假交易类诈骗", "网络游戏虚假交易类诈骗", "游戏账号 道具 点卡 免费领取 私下交易 解冻费 注册费"),
    ("10_hunlian", "婚恋、交友类诈骗", "婚恋交友类诈骗", "网恋 交友 外国军人 遭遇变故 急用钱 杀猪盘"),
    ("11_jipiao", None, "机票退改签类诈骗", "航班取消 延误 改签 赔偿 航空公司客服 屏幕共享"),
]


def lines(name):
    return [l.strip() for l in (HERE / "sources" / name).read_text(encoding="utf-8").split("\n") if l.strip()]


def section_2024(title):
    ls = lines("mps2024_top10_tacheng.txt")
    heads = [t[1] for t in TYPES if t[1]]
    i = ls.index(title)
    j = next((k for k in range(i + 1, len(ls)) if ls[k] in heads or ls[k].startswith("【关闭窗口】")), len(ls))
    body = [l for l in ls[i + 1:j]]
    desc = "\n\n".join(l for l in body if not l.startswith("【典型案例"))
    case = "\n\n".join(l for l in body if l.startswith("【典型案例"))
    return desc, case


def section_2025(title):
    ls = lines("mps2025_top10_embassy.txt")
    k = next(i for i, l in enumerate(ls) if re.match(r"^\d\d", l) and l[2:] == title)
    return ls[k + 1]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.md"):
        old.unlink()
    for fname, t24, t25, kw in TYPES:
        name = t24 or t25
        texts = []
        if t24:
            texts += list(section_2024(t24))
        if t25:
            texts.append(section_2025(t25))
        kw = " ".join(k for k in kw.split() if any(k in x for x in texts))
        parts = [f"# 防骗话术｜{name}", "", f"- 类型：{name}", f"- 常见用语（取自原文）：{kw}",
                 "- 性质：公安部公开发布的高发电信网络诈骗类型说明，正文逐字摘录，未改写", f"- 访问日期：{ACCESS}", ""]
        if t24:
            desc, case = section_2024(t24)
            parts += [f"## 手法说明（{SRC24[0]}）", "", f"来源：{SRC24[1]}", "", desc, ""]
            if case:
                parts += ["## 典型案例（同一来源）", "", case, ""]
        if t25:
            parts += [f"## 作案环节（{SRC25[0]}，条目：{t25}）", "", f"来源：{SRC25[1]}", "", section_2025(t25), ""]
        parts += ["使用说明：以上为公安部公开发布的手法说明，用于帮助识别话术。是否构成诈骗由公安机关依法认定；"
                  "遇到疑似诈骗应立即停止转账，并联系发卡银行、拨打 96110 或 110。"]
        (OUT / f"scam_{fname}.md").write_text("\n".join(parts) + "\n", encoding="utf-8", newline="\n")
    print(f"已生成 {len(TYPES)} 个文件到 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
