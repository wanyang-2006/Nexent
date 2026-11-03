"""统计检索测试集的命中率。

用法：python kb/rag_eval/score_retrieval.py results.csv
results.csv 列：id, top1, top2, top3, top4, top5（填 Nexent 检索返回的文档名，不带 .md，没有就留空）。
只统计 type 为 直接/改写/综合/跨库/案例 的题；越界题单独列出，人工判断。
指标：Hit@1、Hit@3、Hit@5、MRR。跨库和多文件题要求任一期望文件出现即算命中，并另报“全部期望文件都出现”的比例。
"""
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def norm(s: str) -> str:
    s = s.strip()
    return s[:-3] if s.endswith(".md") else s


def main(path: str) -> int:
    gold = {r["id"]: r for r in csv.DictReader((HERE / "retrieval_testset.csv").open(encoding="utf-8"))}
    got = {r["id"]: [norm(r.get(f"top{i}") or "") for i in range(1, 6)] for r in csv.DictReader(open(path, encoding="utf-8-sig"))}
    n = h1 = h3 = h5 = full5 = 0
    mrr = 0.0
    miss = []
    for qid, g in gold.items():
        if g["type"] == "越界" or qid not in got:
            continue
        exp = {norm(x) for x in g["expected_files"].split(";")}
        top = got[qid]
        ranks = [i + 1 for i, d in enumerate(top) if d in exp]
        n += 1
        if ranks:
            r = min(ranks)
            h1 += r <= 1; h3 += r <= 3; h5 += r <= 5; mrr += 1 / r
        else:
            miss.append((qid, g["query"], sorted(exp), top))
        full5 += exp <= set(top)
    if not n:
        print("没有可统计的题"); return 1
    print(f"题数 {n}  Hit@1 {h1/n:.1%}  Hit@3 {h3/n:.1%}  Hit@5 {h5/n:.1%}  MRR {mrr/n:.3f}  期望文件全部出现 {full5/n:.1%}")
    for m in miss:
        print("未命中", *m, sep=" | ")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
