from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "赛题3申请表.docx"
SOURCE = next(ROOT.glob("【赛题3】*.docx"))
TITLE = "基于仿真交易图的涉诈资金链路识别与证据工单辅助研判"

INTRO = [
    "本作品面向银行反诈与风控分析、反诈业务培训场景，针对涉诈资金多层转账、分散汇入和拆分转出导致的路径难还原、证据难核对、规则调整后重复复核等问题，基于华为ModelEngine Nexent构建“涉诈资金链路研判助手”。",
    "系统结合交易方向、时间窗和资金守恒识别资金链，支持账户研判、已有工单查询、规则版本比较及监管依据问答。自研算法完成追链、规则判断和工单生成，智能体按流程调用工具并检索规则、案例与法规，将结论对应至交易编号、规则出处、反向证据和缺失材料；规则更新后可列出结论变化的账户及原因，帮助分析人员核对与复核。",
    "在300个账户、2973笔交易的合成数据集上，规则v2识别全部12条埋入资金链，链边召回率100%、精确率96.6%，63个干扰账户均未被判为“建议人工复核”。结果仅适用于本作品仿真场景，系统提供辅助研判意见，供人工复核参考。",
]

TECH = [
    (
        "1. 智能体设计与编排：",
        "基于华为ModelEngine Nexent的Python CodeAgent构建单智能体，接入DeepSeek-V4.1-Flash；通过研判、规则更新重判、证据引用3个Skill约束执行顺序和输出格式，分步调用工具并核对返回结果。",
    ),
    (
        "2. MCP工具与算法：",
        "以FastMCP将账户查询、流水查询、追链、规则检查、工单生成与读取、版本重判封装为7个业务工具。依据时间窗与资金守恒构建交易链接图，保留并行汇入结构；以YAML管理11条风险及反向规则，支持版本化计算与全量重判。",
    ),
    (
        "3. 知识接入与证据核验：",
        "使用Qwen3-Embedding-4B向量化，接入仿真规则、公开案例、监管文件和反电诈法条文4个知识库，通过RAG检索具体条目。答复区分工具事实和规则来源，保留交易编号、反向证据与信息缺口。",
    ),
    (
        "4. 调试评估与部署：",
        "结合离线评测、基线对照、87项自动化测试和平台回归优化流程，累计发布11个智能体版本。MCP服务部署于阿里云ECS，经SSE接入Nexent，由systemd常驻运行；已完成同租户配置导出与恢复验证，形成场景分析、设计编排、调试优化、部署验证的完整流程。",
    ),
]


def set_font(run, bold=False):
    run.font.name = "微软雅黑"
    run.font.size = Pt(12)
    run.font.bold = bold
    run.font.color.rgb = RGBColor(0, 0, 0)
    fonts = run._element.get_or_add_rPr().rFonts
    for key in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn(f"w:{key}"), "微软雅黑")


def format_paragraph(paragraph, *, centered=False, heading=False, indent=False):
    paragraph.style = "Normal"
    fmt = paragraph.paragraph_format
    fmt.alignment = WD_ALIGN_PARAGRAPH.CENTER if centered else WD_ALIGN_PARAGRAPH.JUSTIFY
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(5 if heading else 3)
    fmt.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    fmt.line_spacing = Pt(19)
    fmt.first_line_indent = Pt(24 if indent else 0)
    fmt.keep_with_next = heading
    fmt.keep_together = True
    fmt.widow_control = True
    pr = paragraph._p.get_or_add_pPr()
    ind = pr.find(qn("w:ind"))
    if ind is not None:
        for key in ("firstLineChars", "hangingChars", "leftChars", "rightChars"):
            ind.attrib.pop(qn(f"w:{key}"), None)
    snap = pr.find(qn("w:snapToGrid"))
    if snap is None:
        snap = OxmlElement("w:snapToGrid")
        pr.append(snap)
    snap.set(qn("w:val"), "0")


def fill_cell(cell, text, *, centered=True):
    cell.text = ""
    paragraph = cell.paragraphs[0]
    format_paragraph(paragraph, centered=centered)
    paragraph.paragraph_format.space_after = Pt(0)
    set_font(paragraph.add_run(text))
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def fill_section(cell, title, entries):
    cell.text = ""
    heading = cell.paragraphs[0]
    format_paragraph(heading, centered=True, heading=True)
    set_font(heading.add_run(title), bold=True)
    for entry in entries:
        paragraph = cell.add_paragraph()
        format_paragraph(paragraph, indent=isinstance(entry, str))
        if isinstance(entry, str):
            set_font(paragraph.add_run(entry))
        else:
            set_font(paragraph.add_run(entry[0]), bold=True)
            set_font(paragraph.add_run(entry[1]))
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP


def main():
    intro_length = len("".join(INTRO))
    assert intro_length <= 500, intro_length
    source = Document(SOURCE).tables[0]
    team = source.cell(2, 1).text.strip()
    leader, member_one, member_two = [source.cell(4, i).text.strip() for i in (2, 3, 4)]
    assert team == "ModelCrafter"
    assert (leader, member_one, member_two) == ("万阳", "刘定佳", "何菁蔓")

    doc = Document(TARGET)
    table = doc.tables[0]
    fill_cell(table.cell(0, 1), "未参赛（  ）    赛题1（  ）    赛题2（  ）    赛题3（√）")
    fill_cell(table.cell(1, 1), TITLE)
    fill_cell(table.cell(2, 1), team)
    fill_cell(table.cell(4, 1), leader)
    # The supplied template has three member cells for a maximum of two members.
    fill_cell(table.cell(4, 2), member_one)
    member_cell = table.cell(4, 3).merge(table.cell(4, 4))
    fill_cell(member_cell, member_two)
    fill_section(table.cell(5, 0), "作品介绍", INTRO)
    fill_section(table.cell(6, 0), "应用的技术", TECH)

    for row in table.rows:
        pr = row._tr.get_or_add_trPr()
        if pr.find(qn("w:cantSplit")) is None:
            pr.append(OxmlElement("w:cantSplit"))
    doc.save(TARGET)
    print(f"Introduction characters: {intro_length}")
    print(f"Technology characters: {sum(len(a) + len(b) for a, b in TECH)}")
    print(f"Saved: {TARGET}")


if __name__ == "__main__":
    main()
