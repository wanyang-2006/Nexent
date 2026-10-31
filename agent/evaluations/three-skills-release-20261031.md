# 三技能正式版发布与验收（2026-10-31）

正式智能体为 agent_id=1 / fundtrace_agent，当前平台版本 V9，发布名称 `fundtrace-v1.2-三技能-20261031`。绑定 fund-chain-investigation、evidence-citation、rule-update-rejudge；规则版本仍为 v1/v2，与平台版本号不同。仅处理完整合成数据，不是真实银行数据。

## 本轮修改

- 将分散补丁合并为完整提示词，源文件为 `../prompt_real.md`；候选留档为 `../prompt_three_skills_final.md`。三个提示词字段与发布 V9 逐字核对一致。
- 单账户先加载证据技能、再加载研判技能；版本比较先加载证据技能、再加载重判技能；只读已有工单先加载证据技能，再 get_ticket；纯规则问答不执行业务工具。
- 账户事实和规则知识引用分区。末端只表示当前数据窗口和追踪深度内可见末端，保留状态、反向证据、缺口与工单建议动作。
- 保留模型 DeepSeek-V4.1-Flash、max_steps=15、enable_protocol_repair_retry=true、七个业务工具与知识检索、两个知识库索引。未改 MCP 后端、数据、知识库或平台记忆设置。

## 最终草稿回归

在正式智能体1的草稿上，使用 `eval/nexent_evalset.md` 原五题，每题三次独立请求，共15次。history=[]、is_debug=false、deep_thinking=false，不向运行时提供预期答案。全部 HTTP 200、有最终答复，无流错误或执行异常。

| 题目 | 次数 | 核心核对结果 |
|---|---:|---|
| A0209/v1 研判与工单 | 3 | REVIEW、中转端、L-T01908、五条链边及金额、反向/缺失证据 |
| A0044/v1 去向 | 3 | RISK_SIGNAL、疑似受骗付款端、五条真实边、并行汇入、A0186及窗口/深度边界 |
| A0105/v1 正常与工资反证 | 3 | CLEAR、无链、R09/T01736/8094元、GAP_KYC/GAP_BIZ、空建议动作 |
| R01/v1与v2定义 | 3 | 60→120分钟、90%至110%、10000元、只检索知识库 |
| v1→v2及A0176/v2工单 | 3 | 300户、8变化/8升级/0降级、八户完整状态与链号、工单及三笔证据 |

实际逐调用核对 **51份业务JSON**，去除 `_demo` 后与本地 `core.api` 一致；get_ticket预期在临时目录生成，未覆盖仓库既有工单。此前进度消息及平台发布说明中的“56份”是统计误写，以本报告和逐次JSON中的51份为准。

14/15次严格自动检查无告警。R2Q3保留自动FAIL告警 `account facts in rule definitions`：检查器把横线后的无引用小结算入规则区；人工核对该小结的账户、状态、工资交易及金额与工具一致，且没有知识库引用。按业务事实和引用归属验收通过，但不宣称严格两区格式15/15通过。

所有应加载技能的请求均按证据技能→业务技能→首个业务调用的顺序执行；工具事实区未出现知识库引用标记。此次为固定五题的有限样本验证，不证明任意问题均可靠，也不要求逐字输出一致。

详细结果：`regression/three-skills-release-20261031-checks.json`，保留自动告警及人工复核。

## 发布版普通请求复测

发布V9后以明确的version_no=9、is_debug=false、空历史再次执行五道原题，5/5自动事实与路由核对通过，17份业务JSON与本地一致。另补两项：

- 查看A0209/v1已有工单：实际调用read_skill_md(evidence-citation)→get_ticket，未make_ticket或重新研判，返回与本地临时工单预期一致。
- A9999不存在账户：实际加载两个前置技能→get_account，收到ACCOUNT_NOT_FOUND后停止，未调用流水、追链、规则、生成工单。

两项边界返回均与本地一致，总计发布后7次请求、19份业务返回。原始请求经浏览器同源 `/api/agent/run` 发起，未另外声称完成输入框端到端操作或截图验收。详细结果为 `regression/three-skills-v9-published-20261031-checks.json` 及 `regression/three-skills-v9-boundaries-20261031.json`。

## 保留的失败与限制

- 更早三技能版本执行成功但人工发现引用、去向边界及一次加载顺序问题，见 `three-skills-regression-20261031.md`，不能与最终候选混算。
- 最终候选在测试智能体3的首组回归仅完成14次，第15次在HTTP200后发生 `TypeError: Failed to fetch`；原始流和元数据保留在工作区，不计作15/15。之后在智能体1草稿重新完成本报告的独立15次。未确定网络中断原因。
- 正文仍存在少量格式或来源措辞瑕疵：R1Q1把trace_chain的total_amount称为工单字段；R1Q3在R09已命中时又补充counter为空的泛化解释；个别答复在规则定义之后追加无引用账户说明。核心值与状态正确，但不能声称文案完全符合严格模板。
- core工单supporting_evidence部分链上非目标账户交易只写“向某账户转出”，未列全实际付款方。完整方向以trace_chain.edges为准。本轮保留后端，不把工单描述补全算作已修复。
- 发布版纯规则问答使用过parallel_executor并行检索，与“一步一工具”文字约束不完全一致，但没有业务工具调用、异常或伪造事实。A0044回答额外描述最大转出，虽可由完整流水核实，也没有严格遵守“不额外求最大值”约束。
- 记忆关闭沿用上轮平台设置；本轮普通请求未出现search_memory。未重新进行全平台记忆设置验收。

## 配置包与交接

`../exports/fundtrace_agent-v9-v1.2-20261031.zip` 包含agent.json和三个Skill ZIP。提示词与V9一致，三个技能正文和元数据语义与本地一致；平台会重排YAML，原研判技能正文还重复一份相同frontmatter，按语义核对，不称字节相同。模型、max_steps、协议修复、八个工具与两个知识库索引均已静态核对。

SHA256：`658A39086AD8B400C9823DD601C0B2530CE0194000DBC180E90237FEF35DA449`。静态记录见 `../exports/fundtrace_agent-v9-verification.json`。新V9包未重新导入；V8同租户恢复测试是历史证据，不能替代V9导入或跨租户迁移验收。

原始SSE与配置核对数据保存在工作区 `.local-playwright/output/`（release-live.json、published-v9-smoke.json、published-v9-config.json及对应逐次文本），未将含租户配置的完整原始流全部纳入Git。仓库中已归档核验结果和最终答复。截图继续按用户要求暂停；甲丙接收确认及全新环境迁移仍需另行完成。用户自行commit/push，本轮未暂存、提交或推送。
