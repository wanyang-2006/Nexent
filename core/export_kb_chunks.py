"""把规则 YAML 渲染成“一条规则一个文件”的知识库语料（RAG 切分用）。

用法（仓库根目录）：
  python -m core.export_kb_chunks                 # 生成 kb/chunks/rules/*.md
  python -m core.export_kb_chunks --out _tmp_kb   # 输出到其他目录（自测）

每个文件只讲一件事，首行固定为“版本｜规则号｜名称”，使检索能区分 v1 与 v2 的同名规则。
条件、参数照抄 YAML，补充说明复用 export_rules_md.NOTES。文件中不放账户号和交易号。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .export_rules_md import FOOTER, NOTES, TYPE_TEXT, _params, _types
from .ruleset import ROOT, list_versions, load_ruleset, resolve_window, rules_diff

SIM = "仿真内部规则，阈值是本作品为仿真场景设定的参数，不是任何监管机构的标准。"


def render_rule(version: str, rs: dict, r: dict) -> str:
    lines = [
        f"# {version}｜{r['rule_id']}｜{r['name']}",
        "",
        f"- 规则集版本：{version}",
        f"- 规则编号：{r['rule_id']}",
        f"- 类型：{TYPE_TEXT[r['type']]}，等级：{r['level']}",
        f"- 条件：{r['desc']}",
    ]
    if _types(r):
        lines.append(f"- 统计范围：{_types(r)}")
    lines += [f"- 参数：{_params(r)}", f"- 依据来源：{r['aligned_to']}"]
    if r["rule_id"] in NOTES:
        lines.append(f"- 说明：{NOTES[r['rule_id']]}")
    lines += ["", f"本条属于{version}。{SIM}"]
    return "\n".join(lines) + "\n"


def render_trace(version: str, rs: dict) -> str:
    tr = rs["trace"]
    rid, param = tr["window_from"].split(".")
    W = resolve_window(rs)
    return "\n".join([
        f"# {version}｜追链参数",
        "",
        f"- 规则集版本：{version}",
        f"- 时间窗：取自 {rid} 的 {param}，{version} 为 {W} 分钟",
        f"- 链边：限{'、'.join(tr['edge_types'])}类交易，单笔不少于 {tr['seed_min_amount']} 元",
        f"- 链内至少有一笔不少于 {tr['min_chain_amount']} 元",
        f"- 节点守恒比例：{tr['conserve_ratio']}",
        "",
        f"本条属于{version}。{SIM}",
    ]) + "\n"


def render_overview(version: str, rs: dict) -> str:
    active = [r for r in rs["rules"] if r.get("state", "active") != "deprecated"]
    items = "\n".join(f"- {r['rule_id']} {r['name']}（{TYPE_TEXT[r['type']]}，{r['level']}）" for r in active)
    return "\n".join([
        f"# {version}｜规则总览",
        "",
        f"- 规则集版本：{version}（基于：{rs.get('based_on') or '无'}）",
        f"- 来源：{rs['source']}",
        "",
        "风险规则命中表示出现某种需要关注的资金特征。反向规则命中表示存在可能说明账户行为正常的证据。"
        "反向规则不单独推翻风险规则，只用于在工单中列出反向证据，并在部分情况下把状态定为“证据不足”。",
        "",
        "本版本包含的规则：",
        items,
        "",
        f"本条属于{version}。{SIM}",
    ]) + "\n"


def render_diff_files(old: str, new: str) -> dict[str, str]:
    ro, rn = load_ruleset(old), load_ruleset(new)
    d = rules_diff(ro, rn)
    by_new = {r["rule_id"]: r for r in rn["rules"]}
    by_old = {r["rule_id"]: r for r in ro["rules"]}
    head = f"# 差异｜{old} 到 {new}｜"
    out: dict[str, str] = {}

    add = [f"- {by_new[a['rule_id']]['rule_id']} {by_new[a['rule_id']]['name']}："
           f"{TYPE_TEXT[by_new[a['rule_id']]['type']]}，{by_new[a['rule_id']]['level']}；"
           f"{by_new[a['rule_id']]['desc']}" for a in d["added"]] or ["无。"]
    out[f"diff_{old}_{new}_added.md"] = "\n".join([head + "新增规则", "", *add, "", SIM]) + "\n"

    chg = [f"- {c['rule_id']} {(by_new.get(c['rule_id']) or by_old[c['rule_id']])['name']}："
           f"字段 {c['field']}，{old} 为 {c['old']}，{new} 为 {c['new']}" for c in d["changed"]] or ["无。"]
    trc = []
    for c in d["trace_changed"]:
        if c["field"] == "W":
            trc.append(f"- 追链时间窗 W：{old} 为 {c['old']} 分钟，{new} 为 {c['new']} 分钟"
                       f"（取自 {rn['trace']['window_from']}）")
        else:
            trc.append(f"- {c['field']}：{old} 为 {c['old']}，{new} 为 {c['new']}")
    out[f"diff_{old}_{new}_params.md"] = "\n".join(
        [head + "参数变化", "", *chg, "", "追链参数变化：", *(trc or ["无。"]), "", SIM]) + "\n"

    rem = [f"- {x['rule_id']} {x['name']}" for x in d["removed"]] or ["无。"]
    out[f"diff_{old}_{new}_removed.md"] = "\n".join([head + "删除规则", "", *rem, "", SIM]) + "\n"

    from .export_rules_md import DIFF_MEANING
    meaning = DIFF_MEANING.get((old, new))
    if meaning:
        out[f"diff_{old}_{new}_meaning.md"] = "\n".join([head + "变化的含义", "", meaning, "", FOOTER]) + "\n"
    return out


def build(out: Path) -> list[Path]:
    files: dict[str, str] = {}
    vs = list_versions()
    for v in vs:
        rs = load_ruleset(v)
        files[f"rule_{v}_overview.md"] = render_overview(v, rs)
        files[f"rule_{v}_trace.md"] = render_trace(v, rs)
        for r in rs["rules"]:
            if r.get("state", "active") == "deprecated":
                continue
            files[f"rule_{v}_{r['rule_id']}.md"] = render_rule(v, rs, r)
    for old in vs:
        for new in [x for x in vs if load_ruleset(x).get("based_on") == old]:
            files.update(render_diff_files(old, new))
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name in sorted(files):
        p = out / name
        with p.open("w", encoding="utf-8", newline="\n") as f:
            f.write(files[name])
        written.append(p)
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="规则 YAML → 一规则一文件的知识库语料")
    ap.add_argument("--out", type=Path, default=ROOT / "kb" / "chunks" / "rules")
    a = ap.parse_args(argv)
    ps = build(a.out)
    print(f"已生成 {len(ps)} 个文件到 {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
