"""甲的一键核验脚本：把分散的校验命令串成一条，最后给出通过/失败汇总。

用法（仓库根目录，Windows PowerShell 或 Linux 均可）：
  python core/run_checks_jia.py            # 全部步骤
  python core/run_checks_jia.py --fast     # 跳过较慢的 pytest 与埋链核对
  python core/run_checks_jia.py -v         # 打印每一步的完整输出

步骤：
  1 环境       Python 版本与依赖（pyyaml、jsonschema、referencing、pytest）
  2 规范自检   validate_spec.py：枚举、规则 YAML、生成配置、examples 样例
  3 fixtures   core/fixtures 与样例数据一致（乙的 fixture 模式依赖它）
  4 数据与防泄题 data/ 的格式与 sha256（确认冻结数据未被改动），工具代码未引用答案目录
  5 埋链核对   verify_injected_chains.py：12 条链与 D3 符合生成配置
  6 单元测试   pytest tests -q（六个函数的契约与正确性）
  7 规则文档   export_rules_md 重新生成 kb/rules_v1.md、rules_v2.md、rules_diff_v1_v2.md
  8 自检       selfcheck 写出 selfcheck_v1.txt、selfcheck_v2.txt
  9 评测       evaluate 写出 result.md
  10 工单      为演示账户生成 v1、v2 工单并用 validate_spec.py 校验

完整日志写到 _tmp_checks/run_checks_jia_log.txt（_tmp*/ 已在 .gitignore 中）。
本脚本不读取答案目录；需要答案的步骤由白名单脚本（selfcheck、evaluate、verify_injected_chains）自己读取。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# 以 `python core/run_checks_jia.py` 运行时 sys.path[0] 是 core/，其中的 trace.py 会遮住标准库 trace；换成仓库根目录
sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != ROOT / "core"]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SPEC = "Data and Rules/validate_spec.py"
DEMO_ACCOUNTS = ["A0209", "A0044", "A0105", "A0176", "A0074", "A0015", "A0146", "A0127", "A0104", "A0168"]
LOG_DIR = ROOT / "_tmp_checks"

try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass


def _env():
    e = dict(os.environ)
    e["PYTHONUTF8"] = "1"
    e["PYTHONIOENCODING"] = "utf-8"
    e.pop("FUNDTRACE_DATA_DIR", None)          # 一律用正式数据 data/
    e.pop("FUNDTRACE_TICKET_DIR", None)
    return e


def run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=ROOT, env=_env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout.decode("utf-8", errors="replace")


def py(*args) -> list[str]:
    return [sys.executable, *args]


def step_env() -> tuple[int, str]:
    lines = [f"Python {sys.version.split()[0]}（{sys.executable}）"]
    rc = 0
    if sys.version_info < (3, 11):
        lines.append("需要 Python 3.11 及以上")
        rc = 1
    from importlib import metadata
    for mod, dist in (("yaml", "PyYAML"), ("jsonschema", "jsonschema"), ("referencing", "referencing"), ("pytest", "pytest")):
        try:
            __import__(mod)
            try:
                ver = metadata.version(dist)
            except metadata.PackageNotFoundError:
                ver = ""
            lines.append(f"{mod} {ver}".rstrip())
        except ImportError:
            lines.append(f"缺少 {mod}：pip install pyyaml jsonschema pytest")
            rc = 1
    return rc, "\n".join(lines)


def step_tickets() -> tuple[int, str]:
    os.environ.pop("FUNDTRACE_DATA_DIR", None)
    os.environ.pop("FUNDTRACE_TICKET_DIR", None)
    from core import api
    lines, rc = [], 0
    for v in ("v1", "v2"):
        for a in DEMO_ACCOUNTS:
            tk = api.make_ticket(a, v)
            if "error" in tk:
                rc = 1
                lines.append(f"{v} {a}: 出错 {tk}")
            else:
                lines.append(f"{v} {a}: {tk['status']}，{tk['role']}，{tk['chain_id'] or '不在链上'}")
    for v in ("v1", "v2"):
        r, out = run(py(SPEC, "--skip-spec", "--data", "data", "--tickets", f"tickets/{v}"))
        rc = rc or r
        lines.append(out)
    return rc, "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="甲的一键核验")
    ap.add_argument("--fast", action="store_true", help="跳过 pytest 与埋链核对")
    ap.add_argument("-v", "--verbose", action="store_true", help="打印每一步的完整输出")
    a = ap.parse_args(argv)

    steps = [
        ("1 环境", step_env),
        ("2 规范自检", lambda: run(py(SPEC))),
        ("3 fixtures", lambda: run(py(SPEC, "--skip-spec", "--fixtures", "core/fixtures",
                                      "--data", "Data and Rules/examples/data"))),
        ("4 数据与防泄题", lambda: run(py(SPEC, "--skip-spec", "--data", "data", "--check-leak", "core", "mcp_server"))),
        ("5 埋链核对", None if a.fast else lambda: run(py("core/verify_injected_chains.py"))),
        ("6 单元测试", None if a.fast else lambda: run(py("-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"))),
        ("7 规则文档", lambda: run(py("-m", "core.export_rules_md"))),
        ("8 自检", lambda: run(py("-m", "core.selfcheck"))),
        ("9 评测", lambda: run(py("-m", "core.evaluate"))),
        ("10 工单", step_tickets),
    ]

    LOG_DIR.mkdir(exist_ok=True)
    log, results = [], []
    for name, fn in steps:
        if fn is None:
            results.append((name, "跳过", 0.0))
            print(f"[跳过] {name}")
            continue
        t0 = time.time()
        try:
            rc, out = fn()
        except Exception as e:  # noqa: BLE001
            rc, out = 1, f"{type(e).__name__}: {e}"
        dt = time.time() - t0
        status = "通过" if rc == 0 else "失败"
        results.append((name, status, dt))
        print(f"[{status}] {name}（{dt:.1f} 秒）")
        tail = out.strip().splitlines()
        if a.verbose:
            print(out)
        elif rc != 0:
            print("\n".join("    " + x for x in tail[-40:]))
        elif name.startswith(("8", "1 ")):
            print("\n".join("    " + x for x in tail[-12:]))
        log.append(f"===== {name}：{status}（{dt:.1f} 秒）\n{out}\n")

    (LOG_DIR / "run_checks_jia_log.txt").write_text("\n".join(log), encoding="utf-8")
    failed = [n for n, s, _ in results if s == "失败"]
    print("\n汇总：" + "；".join(f"{n} {s}" for n, s, _ in results))
    print(f"完整日志：{LOG_DIR / 'run_checks_jia_log.txt'}")
    print("结果：全部通过" if not failed else f"结果：{len(failed)} 步失败（{'、'.join(failed)}）")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
