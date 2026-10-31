# FundTrace：基于仿真交易图的涉诈资金链路识别与证据工单辅助研判

第十一届华为 ICT 大赛创新赛赛题 3（基于 Nexent 打造可进化决策智能体）参赛作品。

- 数据全部为**合成数据**；所有结论只表述为“在本作品设定的仿真场景内”。
- 系统只输出**辅助研判工单**，建议动作仅限：建议人工复核、建议关注后续交易、建议补充材料。不定性、不冻结。
- 规则阈值是仿真内部规则，不是官方要求。

## 目录与维护人

| 目录 | 内容 | 维护 |
|---|---|---|
| `Data and Rules/` | 数据、规则、判定与输出规范（权威），校验器 `validate_spec.py` | 甲 |
| `data/` | 冻结的仿真数据集（300 账户、2973 笔交易）；**不得重新生成** | 甲 |
| `core/` | 六个核心函数、追链、规则、工单、重判、评测、基线、链路图、资产登记 | 甲 |
| `eval/` | 答案表、评测结果 `result.md`、对照基线 `baseline.md`、`graphs/` 链路图、`assets_manifest.csv`、演示账户 `demo_accounts.md` | 甲 |
| `tickets/` | 演示账户的 v1、v2 样例工单 | 甲 |
| `ontology/` | 领域本体 | 甲 |
| `tests/` | 单元测试 | 甲 |
| `mcp_server/` | 把核心函数包装成 MCP 工具（供 Nexent 调用）与部署脚本 | 乙 |
| `agent/` | Nexent 智能体的提示词、Skill、测试记录 | 乙 |
| `kb/` | 知识库文档：规则说明（由脚本生成）与 5 篇公开案例摘要 | 乙（规则文件由甲的脚本生成） |

工具代码（`core/` 中除评测与自检外的文件、`mcp_server/`）**不得读取 `eval/`**，由校验器扫描。

## 一键复现

以下命令都在仓库根目录执行，需要 Python 3.11 及以上。

1. 创建环境并安装依赖

```bash
python -m venv .venv
```

Windows 激活：`.venv\Scripts\activate`；Linux/macOS：`source .venv/bin/activate`。

```bash
pip install -r requirements.txt
```

2. 校验规范与数据（含防泄题扫描）

```bash
python "Data and Rules/validate_spec.py" --data data --check-leak core mcp_server
```

3. 一键核验（12 步：规范、fixtures、数据 sha256、埋链、单元测试、规则文档、自检、评测与基线、工单、链路图、资产登记）

```bash
python core/run_checks_jia.py
```

只想快速检查（跳过单元测试与埋链核对）时加 `--fast`。完整日志在 `_tmp_checks/run_checks_jia_log.txt`。

4. 单独生成各项产出（一键核验已包含，改动后可单独重跑）

```bash
python -m core.evaluate
```

写出 `eval/result.md` 与 `eval/baseline.md`。

```bash
python -m core.export_graph
```

写出 `eval/graphs/` 下 4 张演示链路图；加 `--version v1 --chains L-T01908` 可指定。

```bash
python -m core.export_assets_manifest
```

写出 `eval/assets_manifest.csv`，重复运行结果不变。

5. 启动 MCP 服务（供 Nexent 调用）

```bash
MCP_MODE=real MCP_HOST=0.0.0.0 MCP_PORT=8900 MCP_TRANSPORT=sse python mcp_server/server.py
```

`MCP_MODE` 可选 `fixture`（固定样例）、`hybrid`、`real`（读 `data/`）。云端部署与常驻见 `mcp_server/` 下的 `DEPLOY.md`、`SYSTEMD.md`。Windows PowerShell 请先用 `$env:MCP_MODE = "real"` 等方式设置环境变量。

## 结果与数字

所有数字以脚本生成的 `eval/result.md`、`eval/baseline.md` 为准，文档和演示中不要手写与之不一致的数字。演示账户与预期结果见 `eval/demo_accounts.md`。

## 第 5–7 日交付与独立审校（2026-10-31）

甲方材料入口：`eval/handoff/README.md`，含方法、代码摘录、数字表和审校记录。乙方当前基线为平台 V9 `fundtrace-v1.2-三技能-20261031`；规则仍为 v1/v2。评测题目有实际原五题与甲方短题两个版本，不能混用成绩。

```powershell
python core/review_yi_delivery.py
python core/build_jia_delivery.py
```

前者独立核对留档答复的编号并重计调用记录，不能代替原始返回值复放。后者在 `dist/` 生成代码数据包及给丙的材料包，包含逐文件 SHA256，解压后验证哈希、冻结 CSV、源码编译及常见凭据模式。`dist/` 不提交 Git。代码包包含离线评测资料，生产部署按乙方说明排除 `eval/`。

干净检出时保留冻结数据 LF 字节，避免 Windows 自动转换 CSV 换行破坏冻结哈希：

```powershell
git -c core.autocrlf=false clone <仓库地址> fundtrace-clean
```

进入新目录后执行上述创建环境、安装依赖与完整一键核验步骤。Windows 明确使用 `.venv\Scripts\python.exe` 和 `.venv\Scripts\python.exe -m pip` 可避免误用全局环境。不要用重新生成 data 来修复换行问题。

## 注意

- `data/` 已冻结，`python -m core.gen_data --force` 会使账户号失效，需同步更新演示账户并通知乙。
- v2 演示链是专门设计的，用于说明规则变化引起结论变化，不代表真实环境的泛化效果。
- `kb/cases/` 是公开报道的摘要（含来源链接与访问日期），案例 02、03 的上游犯罪不是电信诈骗，对外不要称为“电信诈骗案例”。
- 修改 `core/` 后，先让 `python core/run_checks_jia.py` 全部通过再推送，并通知乙在云端删除旧工单、重启服务。
