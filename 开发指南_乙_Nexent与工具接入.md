# 开发指南（乙）：Nexent 与工具接入

- 适用：华为 ICT 大赛赛题三，校赛一周版。主题《基于仿真交易图的涉诈资金链路识别与证据工单辅助研判》
- 周期：第 1 天 10-29（四）至第 7 天 11-04（三），每天约 6 小时
- 角色：开发乙（Nexent 与工具接入）。搭档开发甲负责数据与算法，文书丙负责文档、视频、答辩
- 只改这些目录：`mcp_server/` `agent/` `kb/`
- 前提：Nexent 平台与所需模型（大语言模型、向量模型）已在 ECS 上配置完成，本文不再讨论平台安装和环境检查
- 配套文档：《开发指南_甲_数据与算法.md》。**接口、规则、编号、枚举、错误码的权威版本在 `Data and Rules/`**（重点读 `README.md`、`03_判定与输出规范.md`、`schemas/`），本文第 2 节只做速查；相对旧约定的改动见 `Data and Rules/CHANGELOG.md`

---

## 0. 评审结论与对原方案的修订

乙的工作线（MCP 工具、智能体、知识库、Skill、联调、导出）在一周内可完成，原方案存在下列问题，已修订。标【改】的以本文为准。

| # | 原方案的问题 | 后果 | 本指南的修订 |
|---|---|---|---|
| 1 | 知识库名写成 `kb_regulations` | Nexent 要求知识库名只能含中文或小写字母，下划线与数字都不行，创建会失败 | 【改】使用 `涉诈规则库`、`涉诈案例库` |
| 2 | 第 2 天建知识库，规则文件第 3 天才产出 | 无内容可传 | 【改】第 2 天先用手工整理的草稿，第 3 天起用甲脚本生成的 `kb/rules_v1.md` 覆盖重传 |
| 3 | 第 3 天换真实函数，甲的追链当天晚上才完成 | 被阻塞 | 【改】甲第 1 天交 `fixtures/`，第 3 天中午交查询函数；乙第 3 天先接查询函数，晚上再接追链 |
| 4 | 提示词只写一整段 | Nexent 的智能体配置分为职责、约束、示例三块 | 【改】第 5 节按三块写 |
| 5 | 智能体“最大步数”没设置 | 研判要连续调用 4 至 5 个工具，默认步数可能不够 | 【改】运行策略里调大，见第 4 天 |
| 6 | 没有对抗“编造交易编号”的手段 | 评审关注决策可溯源 | 【补】`agent/check_ids.py`，把回答中的交易编号（`T\d{5,}`）与账户号回查数据表 |
| 7 | 没有利用 Nexent 自带的智能体评估、版本管理、调用关系图 | 浪费了现成的“调试迭代经验”和“调用关系图”素材 | 【补】第 5 至 6 天加入 |
| 8 | 只写了一个 Skill 的步骤 | 评分项强调 Skill 分层编排 | 【补】三个 Skill：原子、业务、更新类，见第 5 节 |
| 9 | 导出 Agent 配置后没有验证 | 导入后工具与知识库不会自动迁移，提交前可能不可复现 | 【补】第 6 天做一次“导入验证” |
| 10 | 智能体可能联网检索或使用记忆 | 数字来源不可控、演示不可复现 | 【改】不启用互联网搜索工具，关闭记忆功能 |
| 11 | fixtures 由甲手写，字段容易与真实接口不一致 | 第 3 天换真实函数时乙要返工 | 【改】fixtures 直接取 `Data and Rules/examples/fixtures/`，已与 schema 和样例数据一致并通过 `validate_spec.py` 校验 |

---

## 1. 平台功能与工具总表

| 用途 | Nexent 功能 / 外部工具 | 位置 | 本周怎么用 |
|---|---|---|---|
| 自研 MCP 服务 | FastMCP（Python）+ Nexent 远程 MCP 接入 | 智能体开发 → 选择工具 → MCP 配置；或 MCP 仓库 → 我的 MCP → 添加 MCP 服务 → 远程 | 6 个核心工具 + `get_ticket` + `hello`，服务名 `fundtrace` |
| 工具测试 | 工具卡片的“测试”按钮 | 智能体开发 → 工具配置（齿轮） → 工具测试 | 每接入一个工具先单测，再进对话 |
| 知识库 | 知识库配置、`knowledge_base_search` 本地工具 | 知识库页；智能体高级设置选择知识库 | 两个库：`涉诈规则库`、`涉诈案例库` |
| 向量模型 | 已配置的 Embedding 模型 | 建库时选择 | 必须与智能体当前生效的向量模型一致，否则检索失败 |
| Skill | SKILL.md 单文件上传 | Skill 仓库 → 我的 Skill → 创建 Skill → 上传技能文件 | 三个 Skill，见第 5 节 |
| 智能体 | 智能体配置、智能生成、调试、发布、版本管理 | 智能体开发 → 智能体配置 | 一个主智能体 `fund_trace_assistant` |
| 评估 | 智能体评估：评测集、评估器、评估任务 | 智能体开发 → 智能体评估 | 用 5 个演示问题做回归评估（需先发布版本） |
| 调用关系图 | 智能体列表中的“查看调用关系”图标 | 智能体开发 → 选择智能体 | 文档里的调用关系图直接截这个 |
| 导出 | Agent 导出 JSON/ZIP | Agent 仓库 → 我的 Agent → 导出 | 交付物之一 |
| 可选 | 官方技能 `create-docx` | Skill 仓库官方技能 | 把工单导出为 Word（有空再做） |
| 不使用 | 互联网搜索、邮件、终端、记忆 | | 保证数字都来自工具，演示可复现 |
| 数据集 | 不直接使用数据集；工具读甲生成的 `data/*.csv` | | 乙只通过 MCP 调用，不直接读 CSV |
| 开发工具 | Python 3.10+、FastMCP、Git、`curl`、`systemd`（或 `nohup`） | ECS | 见附录 A、B |

---

## 2. 接口速查（权威版本见 `Data and Rules/03_判定与输出规范.md` 与 `schemas/*.schema.json`）

| 工具名 | 参数 | 返回要点 |
|---|---|---|
| `get_account` | `acct_id` | `{acct_id, name, acct_type, open_date, in_count, in_amount, out_count, out_amount, counterparty_count, first_tx_time, last_tx_time}` |
| `get_transactions` | `acct_id`, `start`, `end`, `limit=50`（1 至 200） | **对象**：`{acct_id, start, end, total, count, truncated, transactions: [{tx_id, time, from_acct, to_acct, amount, tx_type, direction}]}`；键名是 `transactions`，按时间升序 |
| `trace_chain` | `acct_id`, `max_hops=4`（1 至 10）, `rule_version="v1"` | `{acct_id, rule_version, window_min, max_hops, chains[]}`；每条链含 `chain_id`（形如 `L-T00412`）、`hops`、`total_amount`、`duration_minutes`、`accounts`、`tx_ids`、`edges`、`roles`、`truncated` |
| `check_rules` | `acct_id`, `rule_version="v1"` | `hits[]` 与 `counter[]`，每项 `{rule_id, rule_name, type, level, evidence_tx_ids, detail}` |
| `make_ticket` | `acct_id`, `rule_version="v1"` | 工单：`ticket_id, spec_version, status, status_code, role, chain_id, conclusion, supporting_evidence[{tx_id, desc}], counter_evidence[{rule_id, rule_name, desc, tx_ids}], missing_evidence[{code, desc}], rule_basis[{rule_id, rule_name, aligned_to}], suggested_actions` |
| `rejudge` | `old="v1"`, `new="v2"` | `changed[]`（含 `direction`、新旧状态/角色/链、`rule_changes`、`reason`）与 `summary{total, changed, upgraded, downgraded, by_transition}` |
| `get_ticket`（乙自写） | `acct_id`, `rule_version="v1"` | 读 `tickets/<版本>/<账户>.json`，不存在则调用 `make_ticket` |

- **错误**：所有工具出错时返回 `{"error": "中文说明", "code": "错误码", "detail": ...}`（`detail` 可选），不抛异常。错误码：`ACCOUNT_NOT_FOUND` / `BAD_RULE_VERSION` / `BAD_TIME_FORMAT` / `BAD_PARAM` / `INTERNAL`。样例：`Data and Rules/examples/fixtures/error.json`。
- **字段兼容**：1.x 内只增不改；`server.py` 与提示词必须容忍多出来的字段。
- **枚举**：`status` 为 未见异常 / 存在风险信号 / 证据不足 / 建议人工复核（代码 CLEAR / RISK_SIGNAL / INSUFFICIENT / REVIEW）；建议动作只允许 建议人工复核 / 建议关注后续交易 / 建议补充材料，由状态唯一决定。
- **编号**：正则允许变宽，账户 `A\d{4,}`、交易 `T\d{5,}`、系统链 `L-T\d{5,}`、工单 `TK-v\d+-A\d{4,}`；`check_ids.py` 不得写死位数。
- **`missing_evidence`** 是对象列表，展示时取 `desc`；第一项固定为 `GAP_KYC`（对手方账户的开户与实名信息）。
- **规则版本**：不做“全局切换状态”，每个工具都带 `rule_version` 参数，智能体按用户说法传 `v1` 或 `v2`，避免多会话互相影响。

自检：`python "Data and Rules/validate_spec.py" --skip-spec --fixtures core/fixtures` 校验乙使用的 fixtures；`--check-leak core mcp_server` 检查代码是否引用了 `eval/`。

---

## 3. 逐日任务

### 第 1 天（10-29）：把第一个 MCP 工具跑通

| 任务 | 时长 | 具体做法 | 完成标准 |
|---|---|---|---|
| 与甲对约定 | 1.5 | 读 `Data and Rules/README.md`、`CHANGELOG.md`、`03_判定与输出规范.md` 第 1、2 节；确认 `get_transactions` 的返回结构、编号、枚举、错误码 | 群里回复“确认” |
| 拉仓库 | 0.5 | `git clone`；在 ECS 上建 `.venv`，`pip install -r requirements.txt` | `python -c "import fastmcp"` 无报错 |
| 只含 `hello` 的 MCP | 2.5 | 见下方步骤 1.1 至 1.4 | Nexent 对话中看到 `hello` 被调用 |
| 7 个假工具 | 1 | 见附录 A 的 `server.py`（6 个函数加 `get_ticket`），设置 `USE_STUB=1`，工具返回 `core/fixtures/*.json`（甲从 `Data and Rules/examples/fixtures/` 复制而来，共 7 个，样例账户为 A0087、A0044 等） | 7 个业务工具在 Nexent 中可见、可测试 |
| 记录环境信息 | 0.5 | 在 `agent/README.md` 记下：MCP 地址、使用的 LLM 与向量模型名称、服务运行方式 | 丙写文档时可直接引用 |

**1.1 写最小服务。** 在 `mcp_server/server.py` 先只放 `hello`：

```python
from fastmcp import FastMCP
mcp = FastMCP("fundtrace")

@mcp.tool(name="hello", description="测试工具：返回问候语")
def hello(name: str) -> str:
    return f"hello {name}"

if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=8900)
```

若所装 fastmcp 版本不接受 `transport="sse"`，查看 `fastmcp` 文档把 `transport` 改成 `"streamable-http"`，Nexent 里的地址后缀随之从 `/sse` 改为 `/mcp`。

**1.2 在 ECS 上运行并本机验证。**

```bash
nohup python mcp_server/server.py > mcp.log 2>&1 &
curl -N -m 3 http://127.0.0.1:8900/sse        # 应看到 event: endpoint，几秒后超时退出属正常
```

**1.3 确定 Nexent 里填的地址。** Nexent 在容器里运行，所以地址不能写 `localhost` 或 `127.0.0.1`。按顺序试，哪个校验通过用哪个：

| 顺序 | 地址 | 说明 |
|---|---|---|
| 1 | `http://<ECS内网IP>:8900/sse` | `ip -4 addr` 查内网 IP。通常可用 |
| 2 | `http://host.docker.internal:8900/sse` | 官方文档推荐写法；Linux 上要求容器配置了 `host-gateway` |
| 3 | `http://172.17.0.1:8900/sse` | Docker 默认网桥网关 |

若都不通：`sudo ufw status` 或 `firewall-cmd --list-all`，只放行 Docker 网段访问 8900；同机访问通常无需改阿里云安全组。**不要把 8900 暴露到公网。**

**1.4 在 Nexent 中注册并测试。**

1. 智能体开发 → 选择智能体的工具 → **MCP 配置**，服务名称填 `fundtrace`（只能含英文字母、数字、下划线、连字符），填入地址，点击添加。也可走“MCP 仓库 → 我的 MCP → 添加 MCP 服务 → 集成类型选远程”，填完后点“连通性校验”再保存。
2. 新建测试智能体，在工具里勾选 `hello`，点工具卡片的“测试”，输入 `name=world`，看返回。
3. 在调试面板发“请调用 hello，名字叫小明”，确认智能体调用成功。

**完成后换成 `server.py` 完整版（附录 A）。** 每次增删工具后，在 Nexent 里“刷新工具”。

截图（交给丙）：MCP 添加成功页、工具列表。

### 第 2 天（10-30）：智能体 v0、知识库、第一个 Skill

| 任务 | 时长 | 具体做法 | 完成标准 |
|---|---|---|---|
| 智能体 v0 | 2 | 见 2.1 | 用假数据走完“查账户 → 追链 → 查规则 → 出工单” |
| 建知识库 | 2 | 见 2.2 | 问“快进快出是什么”能检索到条文 |
| 写 Skill 1 | 1 | 见第 5 节，上传 `fund-chain-investigation` | Skill 在智能体中可选 |
| 截图 | 1 | 工具列表、知识库文件列表、智能体配置页 | 交给丙 |

**2.1 智能体 v0。**

1. 智能体开发 → 智能体配置 → 新建，变量名 `fund_trace_assistant`（字母、数字、下划线，字母开头），展示名“涉诈资金链路研判助手”。
2. 可先在“智能生成”面板描述需求，例如“面向反诈风控人员的资金链路研判助手，使用 fundtrace 的工具查账户、追资金链、核规则、生成工单，回答必须带交易编号，不得认定违法”，生成草稿后“应用到草稿”，再用第 5 节的提示词覆盖。
3. “模型与提示词”：选主力大语言模型；填入第 5 节的职责、约束、示例提示词。
4. “工具与技能”：选择 MCP 里的 `get_account`、`trace_chain`、`check_rules`、`make_ticket`（`get_transactions`、`rejudge`、`get_ticket` 后面再加）；选择本地工具 `knowledge_base_search`。**不选择**互联网搜索类工具。
5. “运行策略”：最大步数调到 10 以上（第 4 天再确认）。
6. 记忆：保持关闭，保证演示可复现。
7. 点击“调试”，输入“帮我研判账户 A0087”（此时返回的是 fixtures 假数据，A0087 为样例中的一级收款端）。

**2.2 建两个知识库。**

| 项目 | `涉诈规则库` | `涉诈案例库` |
|---|---|---|
| 向量模型 | 已配置的文本向量模型，与智能体当前生效的向量模型一致 | 同左 |
| 保留源文件 | 开启（便于重传和溯源） | 开启 |
| 第 2 天内容 | `rules_v1_draft.md`（照 `Data and Rules/02_规则规范.md` 第 3 节的规则表整理）、丙给的法规摘录 | 丙给的 5 个公开案例摘要（每篇一个 `.md`，注明来源） |
| 第 3 天起 | 用甲生成的 `kb/rules_v1.md` 替换草稿 | 无需更改 |
| 第 5 天 | 加 `kb/rules_v2.md`、`kb/rules_diff_v1_v2.md` | 无 |

操作步骤：知识库 → 创建知识库（名称只能是中文或小写字母，不能含数字、空格、下划线）→ 上传文件（支持 `.md/.txt/.csv/.json/.pdf/.docx`，单文件 ≤ 20 MB）→ 等状态变为“已就绪”→ 进入“详细内容”，选 LLM 点“自动总结”并核对描述 → 在 Chunk 详情搜索“快进快出”，确认能看到规则条文。

知识库文件要求：
- 每条规则一个小节，标题含规则编号与名称，例如 `## R01 快进快出`；正文写条件、参数、依据来源、反向证据说明。
- 案例文件每篇 300 至 600 字，写“手法—资金特征—可对应规则”，注明来源链接和访问日期；只做摘要改写，不整篇复制。
- 不放账户号与交易号，避免智能体把知识库内容当作交易证据。

**2.3 绑定知识库。** 智能体配置 → 高级设置 → 知识库，勾选两个库。在工具 `knowledge_base_search` 的配置里确认检索模式为 `hybrid`，点“工具测试”，query 填“快进快出规则的依据”，`index_names` 填两个库名，看返回条目。

**2.4 上传 Skill。** Skill 仓库 → 我的 Skill → 创建 Skill → 上传技能文件，选第 5 节的 `fund-chain-investigation.md`；再到智能体配置的“选择技能”选中并保存。

### 第 3 天（10-31）：接入真实数据

| 任务 | 时长 | 具体做法 | 完成标准 |
|---|---|---|---|
| 接查询函数（中午起） | 1 | 甲中午交付 `get_account`、`get_transactions`；`server.py` 去掉对应工具的 stub，改为调用 `core.api` | 返回真实数据 |
| 部署脚本 | 1 | 写 `restart.sh`（附录 B），可选 `systemd` 单元 | 一条命令能更新并重启 |
| 接追链（晚上） | 1 | 甲交付 `trace_chain` 后替换；工具测试时用 `demo_accounts.md` 里的中转账户 | 返回真实链路 |
| 对话测试 | 2 | 用 5 个账户（3 个诈骗、2 个干扰）问“帮我研判账户 X”，记录到 `agent/test_log.md` | 智能体按顺序调用工具 |
| 知识库换版 | 1 | 用甲生成的 `kb/rules_v1.md` 替换草稿 | 状态“已就绪” |

检查点 1（当晚，与甲一起看）：Nexent 中输入中转账户，返回真实资金链路。

`agent/test_log.md` 表头（后续一直追加，是“调试迭代经验”的原始素材）：

| 日期 | 问题 | 账户 | 智能体/提示词版本 | 工具调用顺序 | 有无编造 | 格式是否正确 | 问题与处理 |
|---|---|---|---|---|---|---|---|

### 第 4 天（11-01）：完整工单

| 任务 | 时长 | 具体做法 | 完成标准 |
|---|---|---|---|
| 接 `check_rules`、`make_ticket` | 2 | 替换 stub；写 `get_ticket`（读 `tickets/<版本>/<账户>.json`，不存在就调 `make_ticket`） | 对话输出完整工单 |
| 提示词定稿 | 2 | 用第 5 节第二版；要求五项齐全、引用交易编号与知识库条文、禁止用语 | 连续 5 次输出格式稳定 |
| 证据编号回查 | 1 | 写 `agent/check_ids.py`（附录 C），把回答复制进去，检查所有交易编号与账户号都存在 | 5 次回答全部通过 |
| 工单展示 | 1 | 让智能体用 Markdown 表格输出，必要时要求“先输出表格，再输出一段 100 字以内的说明” | 展示清楚 |

发布第一个版本：智能体配置 → 发布，版本说明写“v1.0：核心流程”。评估和问答入口只使用已发布版本。

### 第 5 天（11-02）：重判与评估

| 任务 | 时长 | 具体做法 | 完成标准 |
|---|---|---|---|
| 接 `rejudge` | 1.5 | 替换 stub；把 `kb/rules_v2.md`、`kb/rules_diff_v1_v2.md` 上传 `涉诈规则库` | 问“规则升级到 v2，哪些账户结论变了”能回答并说明原因 |
| 写 Skill 2、3 | 1 | 上传 `evidence-citation` 与 `rule-update-rejudge`（第 5 节） | 三个 Skill 都可选 |
| 演示问题测试 | 2 | 5 个演示问题各跑 3 次（见第 6 节），记入 `test_log.md` | 5 个问题稳定可用 |
| 评估任务 | 1.5 | 见下 | 得到一次评估报告截图 |

**Nexent 智能体评估（用于“效果验证”）。**

1. 评测集：智能体开发 → 智能体评估 → 评测集 → 创建，按页面模板填入 5 个演示问题和参考答案要点（例如“应调用 trace_chain 与 check_rules”“应包含工单五项”“不得出现‘诈骗分子’”）。每题一行，避免写死数值。
2. 评估器：选已发布的内置评估器（如答案相关性、响应完整性、内容安全性、运行成功率、工具调用健康度，最多 5 个）。
3. 新建评估任务：选智能体及已发布版本，选评测集和 Judge 模型，运行。
4. 查看汇总和逐条结果，把失败用例的原因写进 `test_log.md`，再改提示词，发布 v1.1，重跑一次，保留两次评估结果截图，作为“调试迭代”的前后对比。

### 第 6 天（11-03）：联调、导出、截图

| 任务 | 时长 | 具体做法 | 完成标准 |
|---|---|---|---|
| 全流程重启测试 | 2 | 重启 MCP 服务（`restart.sh`），刷新 Nexent 工具，清空会话，从头跑 5 个问题 | 一次跑通 |
| 导出与导入验证 | 1.5 | 见下 | 导入的副本也能跑通 |
| 截图 | 1.5 | 按第 6 节清单 | 12 张必需（第 13、14 项可选） |
| 给丙材料 | 1 | 工具清单、智能体配置说明、调用关系图、调试遇到的 3 个问题及解决方法 | 丙确认收到 |

**导出与导入验证。**

1. Agent 仓库 → 我的 Agent → 导出，选 **ZIP**（含技能包），保存到 `agent/`；再导出一份 JSON 备查。
2. 导入前确认依赖：模型已开通、MCP `fundtrace` 已添加、知识库存在。导入不会迁移知识库权限与 MCP，必须手动补。
3. 导入时选择“重新生成”名称或手动改名，检查导入后的工具、知识库、Skill 是否都在，再问一个演示问题。
4. 把“导入后需要手动补的东西”写进 `agent/README.md`：MCP 服务地址与名称、两个知识库及上传文件、模型要求。

### 第 7 天（11-04）：录制与打包

| 任务 | 时长 | 具体做法 | 完成标准 |
|---|---|---|---|
| 配合录视频 | 2 | 按第 6 节演示脚本，丙讲解，乙操作；先清空会话 | 视频完成 |
| 打包 | 1 | `mcp_server/`、`agent/`（含 JSON/ZIP、提示词、Skill 文件、test_log）、`kb/`、部署说明 | 压缩包 |
| 最终检查 | 1 | 文档中的截图与当前系统一致；工具名、知识库名、版本号一致 | 无出入 |
| 机动 | 2 | 突发问题；有空做 `create-docx` 导出工单（可选） | |

---

## 4. 调用链设计（给丙画图，也是演示的预期行为）

```text
用户问题
  └─ 主智能体 fund_trace_assistant
       ├─ Skill: fund-chain-investigation（步骤指引）
       ├─ MCP fundtrace: get_account → trace_chain → check_rules → make_ticket
       ├─ 本地工具 knowledge_base_search: 涉诈规则库、涉诈案例库
       └─ 输出：五项工单 + 证据交易编号 + “基于仿真数据”声明
规则更新：用户说“升级到 v2” → Skill: rule-update-rejudge → rejudge（并按需 make_ticket(…, "v2")）
```

这对应赛题“检索-推理双驱动”：检索侧是知识库（规则条文、案例），推理侧是 MCP（追链、规则计算）。

---

## 5. 智能体提示词与 Skill 全文

### 5.1 提示词（分三块填入配置）

**职责提示词**

```text
你是金融机构反诈风控岗位的“涉诈资金链路研判助手”，帮助研判人员核查账户的资金往来。
所有数据均为仿真数据。你的输出是“辅助研判工单”，最终是否处置由人工决定。

标准流程（用户给出账户号时执行）：
1. 调用 get_account 了解账户基本情况；
2. 调用 trace_chain 追踪资金链路（规则版本默认 v1，用户说 v2 或“升级后”时传 v2）；
3. 调用 check_rules 获取命中的风险规则和反向证据；
4. 用 knowledge_base_search 检索命中规则的说明与相似案例，引用规则编号与条文；
5. 调用 make_ticket 生成工单（同一版本已生成过时可用 get_ticket 读取）；
6. 按“输出格式”回复。
用户询问规则含义时，只检索知识库回答，不调用交易工具。
用户要求“规则升级后哪些结论变了”时，调用 rejudge，并说明变化账户、变化前后状态与原因。
```

**约束提示词**

```text
1. 所有金额、时间、账户号、交易编号必须来自工具返回，禁止编造或推算；工具返回 error 时如实转述 error 的中文说明，不得继续猜测。
2. 每条结论后面必须附至少一个交易编号（形如 T00412）作为证据。
3. 必须同时列出反向证据与“还缺少的证据”；证据不足时写明状态为“证据不足”及缺什么。
4. 不得使用“诈骗分子”“嫌疑人”“洗钱”“违法”等定性词，不得建议冻结、止付、报警、封号。建议动作只能是：建议人工复核、建议关注后续交易、建议补充材料。
5. 不得联网检索，不得使用工具之外的数据。
6. 回答末尾固定写：“本结果基于仿真数据，仅供辅助研判，最终以人工复核为准。”
7. 账户号不在数据中时，直接说明未找到。
```

**示例提示词（输出格式，要求严格遵守）**

```text
## 研判工单：{账户号}（规则版本 {版本}）
| 项目 | 内容 |
|---|---|
| 结论 | {conclusion，含状态与角色} |
| 支持证据 | {交易编号 + 一句话描述，逐条列出} |
| 反向证据 | {规则编号 + 描述；没有则写“未发现”} |
| 还缺少的证据 | {missing_evidence 各项的 desc，逐条列出} |
| 依据规则 | {规则编号、名称、aligned_to；并引用知识库条文片段} |
| 建议动作 | {建议人工复核 / 建议关注后续交易 / 建议补充材料} |

资金链路：{链路编号}，{账户1} → {账户2} → …，共 {n} 跳，历时 {m} 分钟。
本结果基于仿真数据，仅供辅助研判，最终以人工复核为准。
```

### 5.2 Skill 文件（SKILL.md，Front Matter 必须有 `name` 与 `description`，`name` 全英文小写、连字符分隔）

`skills/fund-chain-investigation.md`（业务层）

```markdown
---
name: fund-chain-investigation
description: |
  用于对单个账户做涉诈资金链路研判。当用户给出账户号并要求研判、追踪资金去向或生成工单时使用。
allowed-tools:
  - get_account
  - trace_chain
  - check_rules
  - make_ticket
  - knowledge_base_search
tags: [fraud, investigation]
---
# 资金链路研判

## 步骤
1. get_account(acct_id) 查看基本情况；账户不存在则终止并说明。
2. trace_chain(acct_id, rule_version) 追链；无链路时说明“未识别到资金链路”，继续第 3 步。
3. check_rules(acct_id, rule_version) 获取命中规则与反向证据。
4. 对命中的每条规则，用 knowledge_base_search 在“涉诈规则库”检索条文；再检索“涉诈案例库”找一个相似手法。
5. make_ticket(acct_id, rule_version) 生成工单。
6. 按五项格式输出（结论、支持证据、反向证据、还缺少的证据、依据规则）。

## 输出约束
- 数字与编号只来自工具；证据不足时输出“证据不足”并列出缺什么。
- 只给出“建议人工复核”等建议，不做定性、不建议冻结。
```

`skills/evidence-citation.md`（原子层）

```markdown
---
name: evidence-citation
description: |
  规范证据引用格式。在输出任何结论、工单或解释时使用，确保每条结论都带可核验的交易编号或规则编号。
tags: [evidence]
---
# 证据引用规范
- 交易证据写成：`T00412（2026-03-03 10:05 A0211→A0087 30000 元）`，信息必须来自工具返回。
- 规则依据写成：`R01 快进快出（仿真内部规则v1）`。
- 知识库条文引用写明库名与规则编号，不引用不存在的条文。
- 一条结论无法给出证据编号时，改写为“证据不足”，并写出缺失的证据。
```

`skills/rule-update-rejudge.md`（更新层）

```markdown
---
name: rule-update-rejudge
description: |
  用于规则版本更新后的重新研判。当用户说“切换到 v2”“规则升级后哪些结论变了”时使用。
allowed-tools:
  - rejudge
  - make_ticket
  - knowledge_base_search
tags: [rule-update]
---
# 规则更新与重判
1. 调用 rejudge(old, new)，读取 changed 与 summary。
2. 在“涉诈规则库”检索 rules_diff，说明 v1 到 v2 修改了哪些规则（如 R01 时间窗 60→120 分钟、新增 R11）。
3. 以表格列出变化账户：账户、旧状态、新状态、原因。
4. 选择变化最明显的一个账户，调用 make_ticket(acct_id, "v2") 展示新工单。
5. 说明变化只由规则版本差异引起，不代表账户行为变化。
```

验证 Skill 是否生效：在调试面板提问，观察是否按步骤调用工具。若所用 Nexent 版本中 Skill 不能直接调用 MCP 工具，则以提示词流程为主，Skill 文件保留为“编排说明”，仍可作为交付与截图素材。

---

## 6. 演示问题、验收与截图

### 6.1 五个演示问题（账户号取甲的 `eval/demo_accounts.md`）

| # | 问题 | 预期行为 | 验收 |
|---|---|---|---|
| 1 | 帮我研判账户【中转账户】 | 依次调用 get_account、trace_chain、check_rules、knowledge_base_search、make_ticket，输出五项工单 | 状态为建议人工复核，证据编号全部通过 `check_ids.py` |
| 2 | 追踪账户【受骗付款账户】的钱最后流向了哪里 | trace_chain 返回完整链路，说明各跳账户、金额、时间 | 链路与甲的答案表一致 |
| 3 | 账户【领工资的员工】有风险吗 | 状态未见异常，说明无命中风险规则、有工资入账 | 不被误判 |
| 4 | 快进快出是什么规则？依据是什么 | 只检索知识库，引用 R01 条文与案例，不调用交易工具 | 引用来自知识库 |
| 5 | 规则升级到 v2 后，哪些账户的结论变了，为什么 | 调用 rejudge，列出 ≥ 2 个账户的前后状态与原因；展示一张 v2 工单 | 原因对应 R01 窗口 60→120 分钟或 R11 |

每题至少跑 3 次，状态、证据编号和格式一致才算稳定。

### 6.2 截图清单（1 至 12 必需，13、14 可选）

1. MCP 服务添加成功（连通性校验通过）
2. MCP 工具列表（7 个业务工具）
3. 知识库列表与文件处理状态
4. 智能体配置页（模型、工具、技能、知识库）
5. 提示词（职责、约束、示例）
6. 调用关系图（“查看调用关系”）
7. Skill 列表
8 至 12. 五个演示问题的对话结果
13. 评估任务汇总（v1.0 与 v1.1 前后对比）
14. 版本管理页（版本对比，可选）

### 6.3 演示脚本（3 至 5 分钟视频）

| 时间 | 内容 |
|---|---|
| 0:00 | 一句话介绍问题与系统架构（引用调用链图） |
| 0:30 | 问题 4：规则知识库检索 |
| 1:10 | 问题 1：中转账户完整研判，指出五项与交易编号 |
| 2:10 | 问题 3：工资员工不误判 |
| 2:40 | 问题 5：规则升级到 v2，展示变化账户及原因 |
| 3:40 | 展示评测结果表（甲提供）与后续计划 |

---

## 7. 排错表

| 现象 | 可能原因 | 处理 |
|---|---|---|
| MCP 连通性校验失败 | 地址写成 localhost；服务未监听 0.0.0.0；防火墙；`/sse` 与 `/mcp` 后缀与传输方式不一致 | 按第 1 天 1.3 逐个试地址；`curl` 验证；改 transport 与后缀 |
| 工具列表为空 | 服务名含非法字符；服务未启用；未刷新 | 服务名只用字母数字下划线连字符；点“刷新工具” |
| 智能体不调用工具或直接编造 | 工具描述太含糊；模型能力不够；提示词没写流程 | 工具 description 写清“何时用、返回什么”；换更强的模型；检查最大步数 |
| 工具返回过长、对话变慢 | `get_transactions` 的 `limit` 过大 | 保持默认 `limit=50`（上限 200），看 `truncated` 判断是否还有更多；只用 `tx_ids` 做证据 |
| 知识库检索不到 | 向量模型与智能体当前生效的不一致；文件仍在处理 | 核对向量模型；等待“已就绪”；Chunk 页搜索验证 |
| 知识库创建失败 | 名称含数字、下划线、空格 | 只用中文或小写字母 |
| 输出格式漂移 | 提示词没有固定格式；温度较高 | 把示例块放在“示例提示词”；降低模型随机性；发布前连续 5 次测试 |
| 导入 Agent 后工具缺失 | MCP 与知识库不随导入迁移 | 手动添加 `fundtrace`、重建知识库后再绑定 |
| 评估任务无法选择智能体 | 评估只运行已发布版本 | 先发布 |
| 改了规则 YAML 但对话结果没变 | MCP 服务没重启 | `bash restart.sh`，刷新工具 |

---

## 8. 交接清单

| 时间 | 交给 | 内容 |
|---|---|---|
| 第 2 天 | 丙 | 工具列表、知识库、智能体配置页截图 |
| 第 2 天 | 甲 | 反馈：fixtures 字段不够用之处 |
| 第 3 天 | 甲 | 对话测试问题清单（追链结果异常的账户） |
| 第 5 天 | 甲 | 评估中失败的问题清单 |
| 第 6 天 | 丙 | 工具清单表、智能体配置说明、调用关系图、调试 3 个问题及解决、全部截图 |
| 第 7 天 | 全员 | 打包：MCP 代码、Agent JSON/ZIP、提示词、Skill、知识库文件、test_log、部署说明 |

---

## 附录 A：`mcp_server/server.py` 完整骨架

```python
import json, os, re, sys
from pathlib import Path
from typing import Optional
from fastmcp import FastMCP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
USE_STUB = os.getenv("USE_STUB", "0") == "1"
if not USE_STUB:
    from core import api            # 甲的函数

mcp = FastMCP("fundtrace")

def _fixture(name: str):
    return json.loads((ROOT / "core" / "fixtures" / f"{name}.json").read_text(encoding="utf-8"))

def _call(name, fn, *a, **kw):
    if USE_STUB:
        return _fixture(name)
    try:
        return fn(*a, **kw)          # 甲的函数对已知错误自行返回 {error, code, detail}
    except Exception as e:           # 未预期异常统一包装，不让服务崩溃
        return {"error": "服务内部错误", "code": "INTERNAL", "detail": f"{type(e).__name__}: {e}"}

@mcp.tool(name="hello", description="测试工具：返回问候语")
def hello(name: str) -> str:
    return f"hello {name}"

@mcp.tool(name="get_account",
          description="查询账户基本信息与汇总（类型、开户日期、转入转出笔数与金额、对手方数）。研判的第一步。")
def get_account(acct_id: str) -> dict:
    return _call("get_account", lambda: api.get_account(acct_id))

@mcp.tool(name="get_transactions",
          description="查询账户的交易流水，按时间升序，默认最多 50 条（上限 200）。可用 start/end（格式 YYYY-MM-DD HH:MM）限定范围。返回 total（符合条件总数）、count、truncated 和 transactions 列表。")
def get_transactions(acct_id: str, start: Optional[str] = None, end: Optional[str] = None, limit: int = 50) -> dict:
    # 甲的函数直接返回对象 {acct_id, start, end, total, count, truncated, transactions}，此处不再包装
    return _call("get_transactions", lambda: api.get_transactions(acct_id, start, end, limit))

@mcp.tool(name="trace_chain",
          description="追踪包含该账户的资金链路（时间窗内金额基本守恒的连续转账）。返回链路编号、账户、交易编号、跳数、总金额、时长、各账户角色；truncated=true 表示边数超过 max_hops 已截断。rule_version 取 v1 或 v2，时间窗由该版本规则决定。")
def trace_chain(acct_id: str, max_hops: int = 4, rule_version: str = "v1") -> dict:
    return _call("trace_chain", lambda: api.trace_chain(acct_id, max_hops, rule_version))

@mcp.tool(name="check_rules",
          description="检查账户命中的风险规则和反向证据，每项带证据交易编号。rule_version 取 v1 或 v2。")
def check_rules(acct_id: str, rule_version: str = "v1") -> dict:
    return _call("check_rules", lambda: api.check_rules(acct_id, rule_version))

@mcp.tool(name="make_ticket",
          description="为账户生成研判工单（结论、支持证据、反向证据、缺少的证据、规则依据、建议动作），并保存。rule_version 取 v1 或 v2。")
def make_ticket(acct_id: str, rule_version: str = "v1") -> dict:
    return _call("make_ticket", lambda: api.make_ticket(acct_id, rule_version))

@mcp.tool(name="get_ticket",
          description="读取已保存的工单；不存在则按指定规则版本生成。")
def get_ticket(acct_id: str, rule_version: str = "v1") -> dict:
    if not re.fullmatch(r"v\d+", rule_version) or not re.fullmatch(r"A\d{4,}", acct_id):
        return {"error": "参数格式不正确", "code": "BAD_PARAM", "detail": f"{acct_id}, {rule_version}"}
    p = ROOT / "tickets" / rule_version / f"{acct_id}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return make_ticket(acct_id, rule_version)

@mcp.tool(name="rejudge",
          description="规则版本更新后重新研判全部账户，返回结论发生变化的账户、前后状态与原因，以及汇总。")
def rejudge(old: str = "v1", new: str = "v2") -> dict:
    return _call("rejudge", lambda: api.rejudge(old, new))

if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=8900)
```

说明：

- 工具 `description` 会展示给大模型，要写“什么时候用、返回什么”，这是智能体能否选对工具的关键。
- 日志写文件或 stderr，不要在工具里 `print`。
- `USE_STUB=1 python mcp_server/server.py` 用于第 1 天；去掉该变量即为真实数据。
- 若所装版本的函数装饰器参数略有不同，以 `pip show fastmcp` 后对应文档为准。

## 附录 B：部署脚本

`restart.sh`：

```bash
#!/bin/bash
cd "$(dirname "$0")"
git pull
source .venv/bin/activate
pip install -q -r requirements.txt
pkill -f "mcp_server/server.py" || true
nohup python mcp_server/server.py > mcp.log 2>&1 &
sleep 2
curl -s -N -m 2 http://127.0.0.1:8900/sse | head -n 2
echo "restarted"
```

可选 `systemd`（开机自启、崩溃重启）：`/etc/systemd/system/fundtrace-mcp.service`

```ini
[Unit]
Description=fundtrace MCP
After=network.target
[Service]
WorkingDirectory=/opt/fundtrace
ExecStart=/opt/fundtrace/.venv/bin/python mcp_server/server.py
Restart=always
[Install]
WantedBy=multi-user.target
```

启用：`sudo systemctl daemon-reload && sudo systemctl enable --now fundtrace-mcp`；重启：`sudo systemctl restart fundtrace-mcp`。使用 `systemd` 时 `restart.sh` 中的启动行改为 `sudo systemctl restart fundtrace-mcp`。

## 附录 C：`agent/check_ids.py`（证据编号回查）

```python
import re, sys
import pandas as pd

# 编号位数可变（Data and Rules/enums.yaml 的 id_patterns），不得写死 T\d{5}
TX_RE = re.compile(r"(?<![A-Za-z0-9])T\d{5,}(?!\d)")     # 也会匹配 L-T00412 中的种子交易号，属预期
ACCT_RE = re.compile(r"(?<![A-Za-z0-9])A\d{4,}(?!\d)")   # 也会匹配 TK-v1-A0087 中的账户号

valid_tx = set(pd.read_csv("data/transactions.csv", usecols=["tx_id"], dtype=str)["tx_id"])
valid_acct = set(pd.read_csv("data/accounts.csv", usecols=["acct_id"], dtype=str)["acct_id"])
text = sys.stdin.read() if len(sys.argv) < 2 else open(sys.argv[1], encoding="utf-8").read()

tx_ids = sorted(set(TX_RE.findall(text)))
acct_ids = sorted(set(ACCT_RE.findall(text)))
bad_tx = [i for i in tx_ids if i not in valid_tx]
bad_acct = [i for i in acct_ids if i not in valid_acct]
print(f"交易编号 {len(tx_ids)} 个，不存在 {len(bad_tx)} 个：{bad_tx}")
print(f"账户号 {len(acct_ids)} 个，不存在 {len(bad_acct)} 个：{bad_acct}")
sys.exit(1 if (bad_tx or bad_acct) else 0)
```

用法：把智能体回答存成 `answer.txt`，运行 `python agent/check_ids.py answer.txt`。结果记入 `test_log.md` 的“有无编造”一栏。演示问题中故意询问不存在的账户（如 A9999）时，回答里出现的 A9999 会被报出，属预期，人工核对即可。

工单本身的结构、禁用词、`status_code` 与 `rule_basis` 一致性，用 `python "Data and Rules/validate_spec.py" --skip-spec --data data --tickets tickets/v1` 检查（甲负责，乙在第 4 天抽查）。

## 附录 D：乙的交付物检查表

- [ ] `mcp_server/server.py`、`restart.sh`、（可选）systemd 单元
- [ ] 智能体已发布（至少 v1.0、v1.1），提示词三块与本文一致
- [ ] 两个知识库、文件列表与 `kb/` 一致
- [ ] 三个 Skill 文件已上传并绑定
- [ ] `agent/` 下的 ZIP、JSON、`README.md`（导入后需手动补的资源）、`test_log.md`、`check_ids.py`
- [ ] 评估任务截图（前后两次）
- [ ] 5 个演示问题各连续 3 次稳定
- [ ] 截图 12 张（含可选共 14 张）已交给丙
