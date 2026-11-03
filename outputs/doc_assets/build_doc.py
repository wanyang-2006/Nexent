# 把第一至三章正文写入赛事模板 docx（只替换“第一章”标题之后的正文部分，封面等保持不变）
# 用法：python outputs/doc_assets/build_doc.py <模板.docx> <输出.docx>
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image

from content import ABSTRACT, CH1, CH2, CH3, TECH

ASSETS = Path(__file__).resolve().parent
FONT = '<w:rFonts w:hint="eastAsia" w:ascii="微软雅黑" w:hAnsi="微软雅黑" w:eastAsia="微软雅黑"/>'
MONO = '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:eastAsia="微软雅黑"/>'
TEXT_W = 8306  # A4 减去左右页边距（twips）


def runs(text, sz=21, bold=False):
    """`...` 内的片段用等宽字体，其余用微软雅黑。"""
    out = []
    for i, seg in enumerate(text.split("`")):
        if not seg:
            continue
        font = MONO if i % 2 else FONT
        b = "<w:b/>" if bold else ""
        out.append(f'<w:r><w:rPr>{font}{b}<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/></w:rPr>'
                   f'<w:t xml:space="preserve">{escape(seg)}</w:t></w:r>')
    return "".join(out)


def para(text, indent=True, sz=21, align=None, bold=False, before=0, after=60, keep=False):
    ind = '<w:ind w:firstLineChars="200" w:firstLine="420"/>' if indent else ""
    jc = f'<w:jc w:val="{align}"/>' if align else ""
    kn = "<w:keepNext/>" if keep else ""
    return (f'<w:p><w:pPr>{kn}<w:spacing w:before="{before}" w:after="{after}" w:line="360" w:lineRule="auto"/>'
            f'{ind}{jc}<w:rPr>{FONT}<w:sz w:val="{sz}"/></w:rPr></w:pPr>{runs(text, sz, bold)}</w:p>')


def heading(text, level):
    # level 3 = 模板“标题 3”（styleId 4），level 2 = “标题 2”（styleId 3）；编号手写，关闭自动编号
    sid = {2: "3", 3: "4"}[level]
    sz = "24" if level == 2 else "22"
    return (f'<w:p><w:pPr><w:pStyle w:val="{sid}"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="0"/></w:numPr>'
            f'<w:ind w:left="0" w:firstLine="0"/><w:rPr>{FONT}<w:sz w:val="{sz}"/></w:rPr></w:pPr>'
            f'{runs(text, int(sz), bold=True)}</w:p>')


def caption(text):
    return para(text, indent=False, sz=18, align="center", after=160)


def table(header, rows, widths):
    total = sum(widths)
    widths = [round(w * TEXT_W / total) for w in widths]
    widths[-1] += TEXT_W - sum(widths)
    border = "".join(f'<w:{s} w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
                     for s in ("top", "left", "bottom", "right", "insideH", "insideV"))
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)

    def cell(text, w, head, keep=False):
        shade = '<w:shd w:val="clear" w:color="auto" w:fill="DCE6F2"/>' if head else ""
        ps = "".join(
            f'<w:p><w:pPr>{"<w:keepNext/>" if keep else ""}<w:spacing w:before="20" w:after="20" w:line="280" w:lineRule="auto"/>'
            f'{"<w:jc w:val=\"center\"/>" if head else ""}<w:rPr>{FONT}<w:sz w:val="18"/></w:rPr></w:pPr>'
            f'{runs(line, 18, bold=head)}</w:p>'
            for line in text.split("\n"))
        return (f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/>{shade}<w:vAlign w:val="center"/></w:tcPr>'
                f'{ps}</w:tc>')

    def row(cells, head=False, keep=False):
        trpr = "<w:trPr><w:tblHeader/><w:cantSplit/></w:trPr>" if head else "<w:trPr><w:cantSplit/></w:trPr>"
        return f'<w:tr>{trpr}' + "".join(cell(c, w, head, keep) for c, w in zip(cells, widths)) + "</w:tr>"

    return (f'<w:tbl><w:tblPr><w:tblW w:w="{TEXT_W}" w:type="dxa"/><w:jc w:val="center"/>'
            f'<w:tblBorders>{border}</w:tblBorders><w:tblLayout w:type="fixed"/>'
            f'<w:tblCellMar><w:left w:w="80" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar>'
            f'<w:tblLook w:val="04A0"/></w:tblPr><w:tblGrid>{grid}</w:tblGrid>'
            + row(header, True, True) + "".join(row(r, keep=len(rows) <= 6 and i < len(rows) - 1) for i, r in enumerate(rows)) + "</w:tbl>"
            + para("", indent=False, sz=12, after=0))


def code(lines):
    shade = '<w:shd w:val="clear" w:color="auto" w:fill="F3F4F6"/>'
    out = []
    for i, l in enumerate(lines):
        kn = "<w:keepNext/>" if i < len(lines) - 1 else ""
        out.append(f'<w:p><w:pPr>{kn}<w:keepLines/>{shade}<w:spacing w:before="0" w:after="0" w:line="260" w:lineRule="auto"/>'
                   f'<w:ind w:left="200"/><w:jc w:val="left"/></w:pPr><w:r><w:rPr>{MONO}<w:sz w:val="17"/></w:rPr>'
                   f'<w:t xml:space="preserve">{escape(l)}</w:t></w:r></w:p>')
    return "".join(out) + para("", indent=False, sz=12, after=0)


class Images:
    def __init__(self):
        self.items = []

    def add(self, path, width_cm):
        idx = len(self.items) + 1
        rid = f"rIdImg{idx}"
        w, h = Image.open(path).size
        cx = int(width_cm * 360000)
        cy = int(cx * h / w)
        self.items.append((rid, Path(path), f"image{idx}{Path(path).suffix}"))
        return (f'<w:p><w:pPr><w:keepNext/><w:spacing w:before="120" w:after="60"/><w:jc w:val="center"/></w:pPr><w:r><w:drawing>'
                f'<wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
                f'<wp:docPr id="{100 + idx}" name="图片{idx}"/>'
                f'<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                f'<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
                f'<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
                f'<pic:nvPicPr><pic:cNvPr id="{idx}" name="{escape(Path(path).name)}"/><pic:cNvPicPr/></pic:nvPicPr>'
                f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
                f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
                f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
                f'</a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')


def render(blocks, imgs):
    out = []
    for b in blocks:
        kind = b[0]
        if kind == "p":
            out.append(para(b[1], align="left" if "`" in b[1] else None, keep=b[1].endswith("：")))
        elif kind == "pn":  # 不缩进段落（参考文献等）
            out.append(para(b[1], indent=False, align="left"))
        elif kind == "h2":
            out.append(heading(b[1], 2))
        elif kind == "h3":
            out.append(heading(b[1], 3))
        elif kind == "lead":  # 表/图前的说明句，与下一块同页
            out.append(para(b[1], keep=True, align="left" if "`" in b[1] else None))
        elif kind == "table":
            out.append(table(*b[1:]))
        elif kind == "tcap":
            out.append(para(b[1], indent=False, sz=18, align="center", after=40, keep=True))
        elif kind == "img":
            out.append(imgs.add(ASSETS.parent.parent / b[1] if not Path(b[1]).is_absolute() else b[1], b[2]))
            out.append(caption(b[3]))
        elif kind == "code":
            out.append(code(b[1]))
        else:
            raise ValueError(kind)
    return "".join(out)


def fill_cell(d, marker, xml):
    """把简介表中含 marker 占位文字的单元格内容换成 xml（保留单元格属性）。"""
    i = d.index(marker)
    start = d.index("</w:tcPr>", max(d.rfind("<w:tc>", 0, i), d.rfind("<w:tc ", 0, i))) + len("</w:tcPr>")
    return d[:start] + xml + d[d.index("</w:tc>", i):]


def main(src, dst):
    work = Path(tempfile.mkdtemp())
    with zipfile.ZipFile(src) as z:
        z.extractall(work)
    doc_p = work / "word/document.xml"
    d = doc_p.read_text(encoding="utf-8")
    paras = list(re.finditer(r"<w:p [^>]*>.*?</w:p>|<w:p>.*?</w:p>", d, re.S))

    def find(text):
        for m in paras:
            if text in "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", m.group(0))):
                return m
        raise KeyError(text)

    ch1, ch2, ch3 = find("第一章 项目设计思路"), find("第二章 代码说明"), find("第三章 参考资料")
    subs = [find("智能体设计背景"), find("agent设计"), find("相关MCP及Skills设计"), find("其他补充")]
    sect = d.index("<w:sectPr", ch3.end())
    imgs = Images()

    body = ch1.group(0)
    for m, blocks in zip(subs, CH1):
        body += m.group(0) + render(blocks, imgs)
    body += ch2.group(0) + render(CH2, imgs)
    body += ch3.group(0) + render(CH3, imgs)
    d = d[:ch1.start()] + body + d[sect:]
    d = fill_cell(d, "项目涉及的关键技术", "".join(para(t, indent=False, align="left", after=20) for t in TECH).replace('w:line="360"', 'w:line="276"').replace("<w:spacing", '<w:snapToGrid w:val="0"/><w:spacing'))
    d = fill_cell(d, "项目概述和简介", "".join(para(t, after=20) for t in ABSTRACT).replace('w:line="360"', 'w:line="300"').replace("<w:spacing", '<w:snapToGrid w:val="0"/><w:spacing'))
    doc_p.write_text(d, encoding="utf-8")

    media = work / "word/media"
    media.mkdir(exist_ok=True)
    rels_p = work / "word/_rels/document.xml.rels"
    rels = rels_p.read_text(encoding="utf-8")
    add = ""
    for rid, path, name in imgs.items:
        shutil.copy(path, media / name)
        add += (f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                f'relationships/image" Target="media/{name}"/>')
    rels_p.write_text(rels.replace("</Relationships>", add + "</Relationships>"), encoding="utf-8")
    ct_p = work / "[Content_Types].xml"
    ct = ct_p.read_text(encoding="utf-8")
    for ext, mime in (("png", "image/png"), ("jpg", "image/jpeg")):
        if f'Extension="{ext}"' not in ct:
            ct = ct.replace("<Default Extension=\"xml\"", f'<Default Extension="{ext}" ContentType="{mime}"/><Default Extension="xml"')
    ct_p.write_text(ct, encoding="utf-8")

    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(work.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(work).as_posix())
    shutil.rmtree(work)
    print("written", dst, "images", len(imgs.items))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
