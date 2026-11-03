"""由 kb/sources/ 中的监管文件原文生成“真实规则库”语料（kb/chunks/real_rules/）。

内容全部逐字取自公开监管文件，不含本作品的仿真阈值、账户号和交易号。
用法（仓库根目录）：python kb/build_real_rules_chunks.py [--out 目录]
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "sources"
ACCESS = "2026-11-02"

N261 = {
    "title": "《中国人民银行关于加强支付结算管理防范电信网络新型违法犯罪有关事项的通知》",
    "no": "银发〔2016〕261号",
    "date": "2016-09-30 成文，2016-12-01 实施（首都之窗标注“有效性：是”；个别条款后续可能被新规调整，引用前须核对现行有效版本）",
    "url": "https://www.beijing.gov.cn/zhengce/zhengcefagui/201905/t20190522_59595.html",
}
ATT = {**N261, "title": N261["title"] + "附件1《涉电信诈骗犯罪可疑特征报送指引》"}
AML = {
    "title": "《金融机构大额交易和可疑交易报告管理办法》（2016 版）",
    "no": "中国人民银行令〔2016〕第3号",
    "date": "2016-12-28 发布，2017-07-01 施行；2025-12-01 另有修订版，本文取自 2016 版，引用前须核对现行有效版本",
    "url": "https://www.efunds.com.cn/Mobile/c/175/175230.shtml",
}

NOTE_FEATURE = ("使用说明：以上为监管文件原文。可疑特征只是识别线索，必须在客户尽职调查的基础上结合多种特征综合判断，"
                "不能单独据此认定账户涉诈；是否报告、处置由金融机构和公安机关依法决定。")
NOTE_RULE = ("使用说明：以上为监管文件原文，规定的是金融机构应履行的义务和处置程序。"
             "引用时写明文件名称、文号和条目；是否报告、处置由金融机构和公安机关依法决定。")
CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
      "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15, "十六": 16}


def num(cn: str) -> str:
    return f"{CN[cn]:02d}"


def chunk(kind: str, label: str, meta: dict, body: str) -> str:
    return "\n".join([
        f"# 真实规则｜{kind}｜{label}",
        "",
        f"- 文件：{meta['title']}",
        f"- 文号：{meta['no']}",
        f"- 时间与效力：{meta['date']}",
        f"- 来源：{meta['url']}",
        f"- 访问日期：{ACCESS}",
        "- 核对状态：正文逐字取自上述公开页面，未改写",
        "",
        "## 原文",
        "",
        body.strip(),
        "",
        NOTE_FEATURE if kind == "可疑特征清单" else NOTE_RULE,
        "",
    ])


def lines(name: str) -> list[str]:
    return [l.rstrip() for l in (SRC / name).read_text(encoding="utf-8").split("\n")]


def attachment_chunks() -> dict[str, str]:
    raw = [l.strip() for l in lines("pbc261_attachment1.txt") if l.strip()]
    out: dict[str, str] = {}
    # 导语：从“涉电信诈骗资金”起到“一、开户环节”之前
    s = next(i for i, l in enumerate(raw) if l.startswith("涉电信诈骗资金"))
    e = next(i for i, l in enumerate(raw) if l.startswith("一、"))
    out["attach1_00_intro"] = chunk("可疑特征清单", "总则：综合判断原则", ATT, "".join(raw[s:e]))
    sec = None
    secname = {"一": "开户环节", "二": "转账交易环节", "三": "取现交易环节"}
    cur: list[str] = []
    items: list[tuple[str, str, str]] = []

    def flush():
        if cur and sec:
            m = re.match(r"（(.+?)）(.*)", "".join(cur))
            items.append((sec, m.group(1), m.group(2)))

    for l in raw[e:]:
        m = re.match(r"^([一二三四])、(.*)", l)
        if m:
            flush(); cur.clear()
            sec = m.group(1)
            if sec == "四":
                out["attach1_9_other"] = chunk("可疑特征清单", "其他", ATT, l)
                sec = None
            continue
        if sec is None:
            continue
        if re.match(r"^（.+?）", l):
            flush(); cur.clear()
        cur.append(l)
    flush()
    key = {"一": "1_open", "二": "2_trans", "三": "3_cash"}
    for sec, no, text in items:
        label = f"{secname[sec]}（{no}）"
        out[f"attach1_{key[sec]}_{num(no)}"] = chunk("可疑特征清单", label, ATT, f"{secname[sec]}（{no}）{text}")
    return out


def notice_chunks() -> dict[str, str]:
    ls = [l for l in lines("pbc261_notice.txt") if l.strip()]
    # 条目标题行形如 “(八)增加转账方式…”；条目内容直到下一个“(X)”或章标题
    starts = [i for i, l in enumerate(ls) if re.match(r"^\([一二三四五六七八九十]+\)", l)]
    chapter = [i for i, l in enumerate(ls) if re.match(r"^[一二三四五六七]、", l)]
    bounds = sorted(set(starts + chapter + [len(ls)]))

    def item(no_cn: str) -> str:
        i = next(k for k in starts if ls[k].startswith(f"({no_cn})"))
        j = next(b for b in bounds if b > i)
        return "\n\n".join(ls[i:j])

    want = [
        ("二", "涉案账户处置", "一、加强账户实名制管理"),
        ("三", "买卖账户与冒名开户的惩戒", "一、加强账户实名制管理"),
        ("六", "异常开户审核与长期无交易账户", "一、加强账户实名制管理"),
        ("八", "转账方式与到账时间", "二、加强转账管理"),
        ("九", "非柜面转账限额与大额提醒", "二、加强转账管理"),
        ("十", "支付账户转账限额", "二、加强转账管理"),
        ("十一", "交易背景调查", "二、加强转账管理"),
        ("十二", "特约商户 T+0 结算", "二、加强转账管理"),
        ("十六", "账户监测与可疑交易处置", "四、强化可疑交易监测"),
    ]
    out = {}
    for no, label, chap in want:
        out[f"notice261_{num(no)}"] = chunk("监管要求", f"{chap}｜第（{no}）项 {label}", N261, item(no))
    return out


def aml_chunks() -> dict[str, str]:
    arts = [l for l in lines("pbc_aml2016_art11_15.txt") if l.strip()]
    out, cur, name = {}, [], None
    for l in arts:
        m = re.match(r"^(第[一二三四五六七八九十]+条)", l)
        if m:
            if name:
                out[name] = "\n".join(cur)
            name, cur = m.group(1), [l]
        else:
            cur.append(l)
    out[name] = "\n".join(cur)
    return {f"aml2016_art{num(k[1:-1])}": chunk("可疑交易报告", k, AML, v) for k, v in out.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=HERE / "chunks" / "real_rules")
    a = ap.parse_args()
    files = {**attachment_chunks(), **notice_chunks(), **aml_chunks()}
    a.out.mkdir(parents=True, exist_ok=True)
    for n, t in files.items():
        (a.out / f"{n}.md").write_text(t, encoding="utf-8", newline="\n")
    print(f"已生成 {len(files)} 个文件到 {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
