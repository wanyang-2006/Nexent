"""把规则 YAML 渲染成知识库 Markdown（02 规范 6.1、6.2 节：知识库文件由脚本生成，不手写）。

用法（仓库根目录）：
  python -m core.export_rules_md                  # 生成 kb/rules_v1.md、kb/rules_v2.md、kb/rules_diff_v1_v2.md
  python -m core.export_rules_md --out _tmp_kb    # 输出到其他目录（自测）

条件文字照抄 YAML 的 desc，参数照抄 params，保证知识库与引擎一致。
NOTES 里是不含数字的补充说明（数字一律来自 YAML）。文件中不放账户号和交易号。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .ruleset import ROOT, list_versions, load_ruleset, resolve_window, rules_diff

TYPE_TEXT = {"risk": "风险规则", "counter": "反向规则"}

# 不含阈值数字的补充说明（数字一律来自 YAML）
NOTES = {
    "R01": "与其他规则共同命中并位于资金链上时，建议人工复核",
    "R02": "高频经营的商户天然会命中本规则，应结合 R10 的反向证据判断",
    "R04": "仿真数据不含账户余额，本规则用当日流入流出比近似余额清零；按自然日（00:00 至 23:59）统计",
    "R05": "开户天数以数据起始日为基准",
    "R07": "跳数指链内最长路径包含的交易笔数；资金链按本版本的追链参数识别",
    "R08": "“首次”只在本数据窗口内判断，窗口之前的历史交易属于缺失证据",
    "R09": "工资入账是反向证据，但不能单独说明账户没有风险；工单中应同时说明需要核实工资发放单位",
    "R10": "命中表示收款特征与日常经营相符，需核实商户经营资质",
    "R11": "规则只看交易特征，不预设对方身份；“首次”只在本数据窗口内判断",
}

DIFF_MEANING = {
    ("v1", "v2"): (
        "时间窗放宽后，资金在账户停留 60 至 120 分钟的“慢一点”的快进快出链路，在 v2 下才会被识别为资金链，"
        "其上的收款账户随之命中链路相关规则，研判状态可能升级。新增的 R11 使得短时间内收到多个陌生对手大额转入的账户多一个风险信号。\n\n"
        "规则放宽也会带来新的待复核对象。例如停留 60 至 120 分钟的普通转发行为，在 v2 下可能被纳入资金链。"
        "这类账户如果同时有工资入账等反向证据，状态为“证据不足”而不是“建议人工复核”，需要补充材料后再判断。"
    ),
}

FOOTER = "不论规则版本如何变化，本系统输出的都是辅助研判结论，处置建议只限于建议人工复核、建议关注后续交易、建议补充材料三种。"


def _types(r: dict) -> str:
    parts = []
    if r.get("in_types"):
        parts.append("转入统计 " + "、".join(r["in_types"]))
    if r.get("out_types"):
        parts.append("转出统计 " + "、".join(r["out_types"]))
    return "；".join(parts)


def _params(r: dict) -> str:
    return "，".join(f"{k} {v}" for k, v in r["params"].items())


def render_rules(version: str) -> str:
    rs = load_ruleset(version)
    tr = rs["trace"]
    W = resolve_window(rs)
    rid, param = tr["window_from"].split(".")
    lines = [
        f"# 涉诈资金链路研判规则 {version}",
        "",
        f"- 规则集版本：{version}（基于：{rs.get('based_on') or '无'}）",
        f"- 来源：{rs['source']}。以下阈值全部为本作品为仿真场景设定的参数，不是任何监管机构的标准。",
        "- 适用数据：仿真交易数据。",
        f"- 本文件由 `core/export_rules_md.py` 从 `Data and Rules/rules/rules_{version}.yaml` 生成，请勿手工修改；规则变化时重新生成并重新上传知识库。",
        "",
        "## 规则类型说明",
        "",
        "风险规则命中表示出现某种需要关注的资金特征。反向规则命中表示存在可能说明账户行为正常的证据。"
        "反向规则不单独推翻风险规则，只用于在工单中列出反向证据，并在部分情况下把状态定为“证据不足”。",
        "",
        "## 追链参数",
        "",
        f"资金链追踪的时间窗取自 {rid} 的 {param}，{version} 为 {W} 分钟。"
        f"链边限{'、'.join(tr['edge_types'])}类交易，单笔不少于 {tr['seed_min_amount']} 元，"
        f"链内至少有一笔不少于 {tr['min_chain_amount']} 元。节点守恒比例为 {tr['conserve_ratio']}。",
    ]
    for r in rs["rules"]:
        if r.get("state", "active") == "deprecated":
            continue
        lines += ["", f"## {r['rule_id']} {r['name']}", "",
                  f"- 类型：{TYPE_TEXT[r['type']]}，等级：{r['level']}",
                  f"- 条件：{r['desc']}"]
        if _types(r):
            lines.append(f"- 统计范围：{_types(r)}")
        lines.append(f"- 参数：{_params(r)}")
        lines.append(f"- 依据来源：{r['aligned_to']}")
        if r["rule_id"] in NOTES:
            lines.append(f"- 说明：{NOTES[r['rule_id']]}")
    return "\n".join(lines) + "\n"


def render_diff(old: str, new: str) -> str:
    ro, rn = load_ruleset(old), load_ruleset(new)
    d = rules_diff(ro, rn)
    by_new = {r["rule_id"]: r for r in rn["rules"]}
    by_old = {r["rule_id"]: r for r in ro["rules"]}
    lines = [
        f"# 规则 {old} 到 {new} 的差异说明",
        "",
        f"- 来源：{rn['source']}",
        f"- 本文件由 `core/export_rules_md.py` 从 `rules_{old}.yaml` 与 `rules_{new}.yaml` 生成，"
        f"与 `python \"Data and Rules/validate_spec.py\" --print-diff {old} {new}` 的结果一致。",
        "",
        "## 新增规则",
        "",
    ]
    if d["added"]:
        lines += ["| 规则 | 名称 | 类型与等级 | 条件 |", "|---|---|---|---|"]
        for a in d["added"]:
            r = by_new[a["rule_id"]]
            lines.append(f"| {r['rule_id']} | {r['name']} | {TYPE_TEXT[r['type']][:2]}，{r['level']} | {r['desc']} |")
    else:
        lines.append("无。")
    lines += ["", "## 删除规则", ""]
    if d["removed"]:
        lines += ["| 规则 | 名称 |", "|---|---|"]
        lines += [f"| {x['rule_id']} | {x['name']} |" for x in d["removed"]]
    else:
        lines.append("无。")
    lines += ["", "## 参数变化", ""]
    if d["changed"]:
        lines += [f"| 规则 | 字段 | {old} | {new} |", "|---|---|---|---|"]
        for c in d["changed"]:
            name = (by_new.get(c["rule_id"]) or by_old[c["rule_id"]])["name"]
            lines.append(f"| {c['rule_id']} {name} | {c['field']} | {c['old']} | {c['new']} |")
    else:
        lines.append("无。")
    lines += ["", "## 追链参数变化", ""]
    if d["trace_changed"]:
        lines += [f"| 字段 | {old} | {new} | 原因 |", "|---|---|---|---|"]
        for c in d["trace_changed"]:
            if c["field"] == "W":
                lines.append(f"| 追链时间窗 W | {c['old']} 分钟 | {c['new']} 分钟 | 追链时间窗取自 {rn['trace']['window_from']} |")
            else:
                lines.append(f"| {c['field']} | {c['old']} | {c['new']} | |")
    else:
        lines.append("无。")
    meaning = DIFF_MEANING.get((old, new))
    if meaning:
        lines += ["", "## 变化的含义", "", meaning]
    lines += ["", FOOTER]
    return "\n".join(lines) + "\n"


def _write(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"已生成 {p}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="把 Data and Rules/rules/*.yaml 渲染成 kb/ 下的规则文档")
    ap.add_argument("--out", type=Path, default=ROOT / "kb", help="输出目录，默认 kb/")
    a = ap.parse_args(argv)
    vs = list_versions()
    for v in vs:
        _write(a.out / f"rules_{v}.md", render_rules(v))
    for old in vs:
        new_rs = [v for v in vs if load_ruleset(v).get("based_on") == old]
        for new in new_rs:
            _write(a.out / f"rules_diff_{old}_{new}.md", render_diff(old, new))
    return 0


if __name__ == "__main__":
    sys.exit(main())
