"""Collect public references; write only inside this research folder."""
import concurrent.futures
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from pypdf import PdfReader

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DATE = "2026-10-26"
CASE_FILE = ROOT / "05_来源核验" / "cases.json"

ASSETS = [
    ("华为ICT第十届官方手册.pdf", "https://e.huawei.com/marketingcloud/pep/asset/20000001/Material/212464e4d94143deaad4b1ee7f9dc55f/M3T1A669N1207723985743143006/%E5%8D%8E%E4%B8%BAICT%E5%A4%A7%E8%B5%9B2025-2026%20%E6%89%8B%E5%86%8C-20251216.pdf", "第十届历史资料；不是第十一届赛题规则"),
    ("腾讯开悟2026人工智能专项赛题.pdf", "https://jwc.njxzc.edu.cn/_upload/article/files/2d/dd/717c626c4df9ac0fa43539f46b63/03c27bbb-f82c-4963-a974-dc84cad867e7.pdf", "高校发布的官方赛题附件，包含智慧法律方向"),
    ("Nexent_README.md", "https://raw.githubusercontent.com/ModelEngine-Group/nexent/main/README.md", "官方仓库README，仅作技术资料；未安装平台"),
    ("Nexent_LICENSE.txt", "https://raw.githubusercontent.com/ModelEngine-Group/nexent/main/LICENSE", "官方许可文本"),
    ("GraphRAG_README.md", "https://raw.githubusercontent.com/microsoft/graphrag/main/README.md", "官方图谱检索基线项目，不是本体动态更新的完整方案"),
    ("GraphRAG_LICENSE.txt", "https://raw.githubusercontent.com/microsoft/graphrag/main/LICENSE", "官方许可文本"),
    ("KAG_README.md", "https://raw.githubusercontent.com/OpenSPG/KAG/master/README.md", "知识增强生成与逻辑推理参考；不得当作自研创新"),
    ("KAG_LICENSE.txt", "https://raw.githubusercontent.com/OpenSPG/KAG/master/LICENSE", "官方许可文本"),
    ("WeKnora_README.md", "https://raw.githubusercontent.com/Tencent/WeKnora/main/README.md", "腾讯开源文档理解参考；平台迁移需自行实现"),
    ("WeKnora_LICENSE.txt", "https://raw.githubusercontent.com/Tencent/WeKnora/main/LICENSE", "官方许可文本"),
    ("FinQA_README.md", "https://raw.githubusercontent.com/czyssrs/FinQA/main/README.md", "金融报告数值推理数据集说明；只下载说明，不代表取得中文行业数据"),
    ("FinQA_LICENSE.txt", "https://raw.githubusercontent.com/czyssrs/FinQA/main/LICENSE", "许可文本，如不存在则记为未取得"),
    ("TATQA_README.md", "https://raw.githubusercontent.com/NExTplusplus/TAT-QA/master/README.md", "表格与文本联合问答数据说明"),
    ("TATQA_LICENSE.txt", "https://raw.githubusercontent.com/NExTplusplus/TAT-QA/master/LICENSE", "许可文本，如不存在则记为未取得"),
]


def fetch(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 ResearchReferenceCollector/1.0"})
    with urlopen(req, timeout=25) as response:
        body = response.read(30 * 1024 * 1024 + 1)
        if len(body) > 30 * 1024 * 1024:
            raise ValueError("resource exceeds 30MB collection limit")
        return body, response.geturl(), response.headers.get("Content-Type", "")


def audit(url):
    result = {"url": url, "checked_on": DATE}
    try:
        body, final, kind = fetch(url)
        soup = BeautifulSoup(body, "html.parser")
        for node in soup(["script", "style", "nav", "footer"]):
            node.decompose()
        text = soup.get_text(" ", strip=True)
        result.update(status="fetched", final_url=final, title=soup.title.get_text(strip=True) if soup.title else "", content_type=kind, text_length=len(text), sha256=hashlib.sha256(body).hexdigest())
        identifiers = ["MAPLE", "合同发票", "一等奖", "特等奖", "二等奖", "银奖", "金奖", "创新奖", "InspectLite", "乐龄", "duoreadme", "Skill Creator", "MindAligner", "HomeAgentMaster", "蛇形", "Nexent", "WeKnora"]
        result["matched_terms"] = [word for word in identifiers if word.lower() in text.lower()]
        # Only retain title and evidence presence, not full copyrighted articles.
        return result
    except Exception as exc:
        result.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        return result


def download(asset):
    name, url, note = asset
    result = {"file": name, "url": url, "purpose": note, "checked_on": DATE}
    target = ROOT / "04_技术与数据" / "已下载资料" / name
    assert target.resolve().is_relative_to(ROOT)
    try:
        body, final, kind = fetch(url)
        if name.endswith(".pdf") and not body.startswith(b"%PDF"):
            raise ValueError("response is not a PDF")
        if not name.endswith(".pdf") and b"<html" in body[:1000].lower():
            raise ValueError("unexpected HTML response")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        result.update(status="downloaded", final_url=final, bytes=len(body), sha256=hashlib.sha256(body).hexdigest(), relative_path=target.relative_to(ROOT).as_posix())
        if name.endswith(".pdf"):
            pdf = PdfReader(target)
            result["pages"] = len(pdf.pages)
            result["relevant_pages"] = [i + 1 for i, p in enumerate(pdf.pages) if any(w in (p.extract_text() or "") for w in ["法律", "蛇形", "病理", "创新赛", "特等奖"])]
    except Exception as exc:
        result.update(status="failed", error=f"{type(exc).__name__}: {exc}")
    return result


def main():
    cases = json.loads(CASE_FILE.read_text(encoding="utf-8"))
    urls = sorted({c[k] for c in cases for k in ["source", "detail"] if c[k].startswith("https://")})
    urls.extend([
        "https://modelengine-group.github.io/nexent/zh/getting-started/overview",
        "https://github.com/ModelEngine-Group/nexent",
        "https://github.com/Tencent/WeKnora",
        "https://github.com/OpenSPG/KAG",
        "https://github.com/microsoft/graphrag",
        "https://github.com/czyssrs/FinQA",
        "https://github.com/NExTplusplus/TAT-QA",
        "https://www.gov.cn/zhengce/",
        "https://www.cninfo.com.cn/",
        "https://www.ccgp.gov.cn/",
        "https://www.samr.gov.cn/",
        "https://openstd.samr.gov.cn/",
        "https://www.nmpa.gov.cn/",
    ])
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        checks = list(pool.map(audit, urls))
    (ROOT / "05_来源核验" / "链接访问记录.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        downloads = list(pool.map(download, ASSETS))
    (ROOT / "05_来源核验" / "下载清单.json").write_text(json.dumps(downloads, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"checked": len(checks), "failed_links": [x["url"] for x in checks if x["status"] == "failed"], "downloads": downloads}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
