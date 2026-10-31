# agent/

智能体目录，由乙维护。存放 Nexent 智能体的提示词、技能、导出配置和测试记录。

## 计划放入的文件

| 文件 | 内容 | 产生时间 |
|---|---|---|
| `README.md`（本文件） | 环境记录：MCP 服务名称与地址、传输方式与端口、所用大语言模型与向量模型、运行命令；导入后需要手动补的资源 | 第 1 天起持续更新 |
| `skills/` | Skill 文件，如 `fund-chain-investigation.md` | 第 2 天 |
| `test_log.md` | 对话测试记录（有无编造、工具调用顺序、问题与修复） | 第 3 天起追加 |
| `check_ids.py` | 把智能体回答里的账户号、交易号回查数据表，防止编造 | 第 3 至 4 天 |
| 导出的 ZIP 与 JSON | Nexent 导出的智能体配置 | 第 5 天以后 |
| 提示词文本 | 职责、约束、示例三块提示词 | 第 2 天起 |

## 当前环境记录（2026-10-31）

- V9 ZIP已完成同租户独立恢复验收：智能体4“资金链研判-V9恢复验收-1031”，显式发布测试V2并绑定三个导入Skill副本。共10次请求、22份业务JSON与本地一致；一次只读正文遗漏保留为失败，两次相同问题复测完整。正式智能体1仍为V9、配置未变。见 [恢复报告](evaluations/v9-restore-20261031.md)。该结果覆盖下方“未重新导入”，不代表跨租户迁移或任意问法稳定。

- 当前正式版为 **V9 / fundtrace-v1.2-三技能-20261031**，三个Skill已绑定并按普通问法加载。最终草稿五题各三次全部完成，51份业务JSON与本地一致；严格自动检查14/15无告警，1条分区告警经人工复核保留。发布版再完成五题及只读工单/异常账户共7次、19份业务返回核对。少量格式与来源措辞限制详见 [最终发布报告](evaluations/three-skills-release-20261031.md)，不称严格模板全部达标。
- 当前提示词为 [prompt_real.md](prompt_real.md)，新备份为 [V9 ZIP](exports/fundtrace_agent-v9-v1.2-20261031.zip)，已静态核对三个Skill及线上配置，未重新导入。截图仍暂停，Git提交推送由用户操作。以下V8及草稿未发布等文字为历史记录，以本段和最终发布报告为准。

- 三技能草稿已跑原五题三轮，15次执行成功、56份业务JSON一致；人工发现去向范围、引用位置和一次加载顺序问题。追加修订后Q2/Q5两次业务复测通过，但引用表达仍待收敛，不能称新配置稳定15/15通过。详见evaluations/three-skills-regression-20261031.md；此条覆盖下方“回归待做”的旧状态。

- 测试副本三技能自动路由已补充到草稿提示词，4次普通问法（2次只读工单、2次版本比较）均实际加载所需技能，5个业务返回与本地一致。仍待新路由单账户完整流程及原五题回归，不代表正式版本已更新。补丁见prompt_three_skills_test.md；详见evaluations/skills-20261031.md，此条覆盖下方先前自动加载限制。

- V8 ZIP已完成同租户隔离副本智能体3导入恢复验收，详见exports/README.md。新增evidence-citation和rule-update-rejudge已在副本草稿绑定；重判修订复测与显式技能只读工单通过，普通工单未自动加载证据Skill，尚未推广正式版。详见evaluations/skills-20261031.md；以下旧V5及“尚未导入”等表述为历史状态。

- 最新发布为平台V8/fundtrace-v1.1-20261030，严格输出协议与静默修复开启，模型仍DeepSeek-V4.1-Flash、最大步数15、记忆关闭。五题各三次独立回归15/15通过，有限样本边界见evaluations/stability-20261030.md。
- 用户已提供开机恢复和SIGKILL异常退出自动恢复证据，NRestarts由0升至1、active/running、real模式8工具19调用自检通过。
- 最新配置备份exports/fundtrace_agent-v8-v1.1-20261030.zip；旧V5 ZIP保留。V8 ZIP已完成同租户导入副本验收，只含原技能，不含10月31日新增技能。以下V5状态属于历史记录。

- 云端用户回传两轮 `PASS: 8 tools; 19 MCP calls; real algorithms on synthetic dataset`，systemd enabled、active。当前 `MCP_MODE=real`，算法处理300账户、2973笔合成交易，不是真实银行记录。
- Nexent `fundtrace_agent` 已绑定七个业务工具（增加 get_ticket、rejudge），以及 fund-chain-investigation Skill；最大步数15。
- 模型：`deepseek-ai/DeepSeek-V4.1-Flash`。两知识库的向量模型均为 `Qwen/Qwen3-Embedding-4B`。
- 已关联涉诈规则库（rules_v1、rules_v2、rules_diff_v1_v2，3文档/7分块）和涉诈案例库（5篇公开报道摘要，5分块）。规则引用来源面板已实测可打开。
- 已同步新版 Skill、使用要求、示例和会话引导。提示词归档：[prompt_real.md](prompt_real.md)。
- 用户明确授权后已关闭Nexent基础设置的记忆能力；独立普通会话原始日志确认不再自动调用search_memory。此为Nexent设置，与Codex自身记忆无关。
- 最新发布Nexent V5，名称 `fundtrace-全算法合成数据-20261030-r2`，补充Python工具执行协议。A0074、A0105、A0176/v1重试和A9999回归已完成；A0105成功轮开启会话深度思考。A0209五个默认参数独立会话完整答复仅3/5通过，两轮分别出现正文截断、DSML调用文本代替执行；当前仍为联调版，稳定性未验收通过。详情及证据见test_log.md。
- 同环境配置备份恢复已通过：独立测试智能体2和Skill副本已导入，A0209/v1、A0176/v2、只读工单、版本比较及异常账户检查通过，原智能体1保留V5。配置ZIP及导入说明见exports/README.md；异环境迁移尚未验收。
- 通用编号核验脚本check_ids.py已完成：5项测试通过，5个演示回复与5次重复回复均完成编号存在性检查。该检查不替代答复完整性和工具执行检查，旧稳定性结果仍为3/5。
- 服务地址、SSE端口、systemd管理命令沿用下方历史记录。不要重新启动 nohup。服务器恢复证据和五次稳定性仍待完成；不要将基础联调通过写成所有开发任务完成。

## 编号核验

交接材料与截图索引：[handoff/README.md](handoff/README.md)。已归档当前配置、工具与Skill、知识库就绪状态、运行策略和记忆关闭截图，完整截图清单尚未完成。

在仓库根目录使用已安装项目依赖的Python执行：

```bash
python agent/check_ids.py answer.md --rule-version v1
python agent/check_ids.py answer.md --rule-version v2 --json
python agent/check_ids.py session-stream.txt --sse-final --rule-version v1
```

省略文件名或使用`-`时读取标准输入。普通文件必须只包含待核验答复；SSE日志必须使用`--sse-final`，仅提取final_answer事件，排除提示词、Skill和工具日志。文件按UTF-8读取，兼容BOM。默认规则版本v1；检查v2答复必须传v2。跨版本比较答复可分别用两个版本运行，并人工判断每条链所属版本。

脚本从Data and Rules/enums.yaml读取可变长度编号格式，通过core.store读取数据表（支持FUNDTRACE_DATA_DIR），通过core.api.trace_chain检查指定版本下的链。链编号内部的种子交易号不重复算作交易引用；工单编号内部的账户号会核验，但不检查工单文件是否存在。全程只读，不生成工单。

退出码：0=提取到的编号全部存在；1=存在未知编号；2=未提取到编号、输入错误或无法核验。A9999等故意查询的不存在账户也会返回1，应人工确认是否为正确的拒答，不能直接记为模型编造。

**PASS仅代表编号存在**，不证明编号与当前账户有关，也不核验金额、时间、方向、规则命中、知识库引用、真实工具执行或答复完整性。DSML文本和截断回复可能通过编号检查，仍应按业务验收判失败。测试与历史答复核验结果见test_log.md。

## 历史环境记录（2026-10-29）

- 工作进度：[开发乙工作清单.md](开发乙工作清单.md)。
- 测试记录：[test_log.md](test_log.md)。
- MCP 服务名称：`fundtrace`。
- 云端项目目录：`/home/Liu/fundtrace-mcp`。
- MCP 地址与传输方式：`http://172.19.25.141:8900/sse`，SSE，端口 8900；Nexent 页面已显示连接成功、已启用、8 个工具。
- FastMCP：4.1.4；云端 Python 为 3.12 系列，完整补丁版本待记录。
- 大语言模型：`deepseek-ai/DeepSeek-V4.1-Flash`，依据用户提供的模型配置截图。
- 向量模型：规则知识库问答已有引用输出，具体 Embedding 名称尚待用户记录，不推测。
- 智能体展示名：涉诈资金链路研判助手；变量名曾建议 `fundtrace_agent`，实际保存值待核实。
- 智能体已绑定工具：get_account、get_transactions、trace_chain、check_rules、make_ticket。
- 当前模式：fixture，仅固定仿真样例；尚未完成 core.api 真实数据联调。
- 云端手动运行命令（历史前台方式，当前改由 systemd 管理，不再重复执行）：

```bash
cd ~/fundtrace-mcp
MCP_MODE=fixture MCP_HOST=0.0.0.0 MCP_PORT=8900 MCP_TRANSPORT=sse \
  .venv/bin/python mcp_server/server.py
```

- 2026-10-29 20:18 CST：用户已在云端安装 fundtrace-mcp.service，输出 enabled、active (running)，进程内与网络自检均通过（8工具、18次调用）。已配置开机启动及进程退出自动重启，不依赖前台终端。实际服务器重启恢复、进程异常退出自动恢复尚未做现场测试。
- 日常管理：`sudo systemctl status fundtrace-mcp --no-pager`；更新代码后 `sudo systemctl restart fundtrace-mcp`；日志 `sudo journalctl -u fundtrace-mcp -n 50 --no-pager`。不要与 nohup 重复启动。
- 规则库素材：`kb/rules_v1_draft.md`，规则问答及与 MCP 联合研判已获得文档引用；引用展开与检索调用记录待留档。
- Skill 文件：`agent/skills/fund-chain-investigation.md` 已创建；用户按上传绑定步骤进行测试，实际技能加载记录尚待留档核实。
- 重新导入时需手动配置模型、MCP 地址与权限、规则知识库及向量模型，并确认 Skill 和工具绑定；配置导出/导入尚未验收。

## 注意

- 提示词要求：编号必须来自工具返回，每条结论带交易编号，列出反向证据和缺失证据，只给三种建议动作，不联网。
- 导入配置后需要手动补的资源（MCP 地址、知识库、模型）都要写在本文件里。
