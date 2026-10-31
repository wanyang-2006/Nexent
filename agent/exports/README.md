# Nexent 配置备份

## 最新V9三技能备份（2026-10-31）

当前正式版为V9 `fundtrace-v1.2-三技能-20261031`，文件 [fundtrace_agent-v9-v1.2-20261031.zip](fundtrace_agent-v9-v1.2-20261031.zip)。SHA256：`658A39086AD8B400C9823DD601C0B2530CE0194000DBC180E90237FEF35DA449`。

ZIP包含agent.json及fund-chain-investigation、evidence-citation、rule-update-rejudge三个Skill ZIP。已核对提示词与正式V9一致、三个技能正文和元数据语义与本地一致（平台会重排YAML，原研判技能重复frontmatter保留）；模型DeepSeek-V4.1-Flash、最大步数15、协议修复true、八个工具和原两个知识库索引均正确。静态核对见 [verification.json](fundtrace_agent-v9-verification.json)，回归与限制见 [发布报告](../evaluations/three-skills-release-20261031.md)。

新V9 ZIP未重新导入实测；V8恢复通过属于历史证据。恢复时重新检查三技能、模型、MCP连通性和目标知识库索引；记忆关闭仍需平台另行配置。ZIP不包含知识库正文/向量、模型凭据、MCP源码/依赖、CSV及工单、systemd或会话历史。包内地址、租户与索引标识仅适用于当前环境，按内部交接配置管理。以下“尚未发布或重新导出”等条目均为历史状态，以本节为准。

2026-10-31边界：新增evidence-citation、rule-update-rejudge仅绑定智能体3草稿，尚未发布或重新导出。下列V8 ZIP仍只含fund-chain-investigation；三技能测试见../evaluations/skills-20261031.md。

## 最新V8备份（2026-10-30）

文件 `fundtrace_agent-v8-v1.1-20261030.zip`，平台发布名称fundtrace-v1.1-20261030。SHA256：`CE3D3091712C5367DC0F95AD703C08BE313C8D545E7D49EA85AEA86F4DFD29BF`。

已用平台导出并检查ZIP结构：agent.json及skills/fund-chain-investigation.zip。agent_info中模型DeepSeek-V4.1-Flash、最大步数15、8个工具（7业务工具加知识检索）、原Skill，enable_protocol_repair_retry=true，提示词包含精简核验约束。角色/使用要求/示例逐字等于线上V8详情，最大步数和修复开关一致。五题独立回归15/15通过，调整后评估记录见../evaluations/。平台ZIP不自带发布版本号，此版本对应关系来自导出时发布版核查。

旧V5/r2备份保留为历史记录，勿以旧包恢复后声称协议修复已开启。V8包已在同一Nexent租户导入为隔离测试智能体并完成恢复验收，结果见“V8同环境导入恢复实测”。迁移资源与敏感标识边界同下文；平台记忆关闭仍需另行配置。

## 历史V5备份

导出日期：2026-10-30。通过 Nexent「我的智能体 → 更多操作 → 导出」下载，平台显示导出成功。

文件：`fundtrace_agent-20261030-r2.zip`。
SHA256：`4BB3FC82513BDC3D071E15C3982467489AE0F7F6D6C6B400331CA9E8A59AAEB3`。

导出时当前发布版本为V5/r2。ZIP自身未携带发布版本号；这是导出时的配置快照，不是全部历史版本备份。当前稳定性实测3/5，仍为联调版，不作为正式v1.0交付。

## 已检查的内容

- `agent.json`：fundtrace_agent、提示词、示例、会话引导、最大步数15、模型名deepseek-ai/DeepSeek-V4.1-Flash。
- 七个MCP业务工具：get_account、get_transactions、trace_chain、check_rules、make_ticket、get_ticket、rejudge。
- knowledge_base_search包含两个当前环境的索引ID、top_k=3、hybrid检索、rerank=false。
- `skills/fund-chain-investigation.zip`：Skill资源压缩包。
- MCP注册信息：fundtrace，`http://172.19.25.141:8900/sse`。
- 当前enable_protocol_repair_retry=false；此处只记录，不在本次备份任务中调整。

## 迁移与恢复

1. 在目标环境部署本仓库MCP，使用real模式对合成数据计算；网络自检显式设置MCP_MODE=real。参阅`../../mcp_server/UPGRADE_REAL.md`和`../../mcp_server/SYSTEMD.md`。
2. 在目标Nexent配置大语言模型及访问凭据。模型名相同不代表目标环境的model_id相同；导入后重新选择并检查模型参数。
3. 创建涉诈规则库，上传`../../kb/rules_v1.md`、`rules_v2.md`、`rules_diff_v1_v2.md`；创建涉诈案例库并按`../../kb/README.md`上传5篇公开报道摘要。两库当前Embedding为Qwen/Qwen3-Embedding-4B，需在目标环境准备该模型并完成索引。
4. 使用「智能体配置 → 导入」选择ZIP。目标MCP地址必须从Nexent后端容器可达；包内172.19.25.141是当前云服务器内网地址，不能假设其他环境可访问。
5. 检查Skill已导入、七个业务工具已绑定、知识库已重新关联目标索引。包内索引ID和tenant_id属于原环境，不可据此认定迁移关联成功。
6. 检查最大步数15及平台记忆能力关闭。记忆能力是平台设置，不能仅靠此ZIP恢复；会话深度思考开关也需单独核对，不视为已固化在发布版。
7. 先在草稿用A0209/v1、A0176/v2、A9999、get_ticket及300账户rejudge回归，再发布。五次稳定性验收仍需修复后重测。

ZIP不包含知识库文档正文、向量索引、模型凭据、MCP服务器源码/依赖、合成数据CSV、工单文件、systemd单元或会话历史。恢复这些内容需配合仓库和服务器备份。

压缩包包含内部地址、租户/索引标识及作者信息，交接时按项目内部配置管理。

## 同环境导入恢复实测（2026-10-30）

### V8配置包恢复复测

- V8 ZIP `fundtrace_agent-v8-v1.1-20261030.zip` 已在同租户导入为隔离副本 `fundtrace_v8_restore_test_20261030`（智能体3），原智能体1及V8未修改。自动创建的V1发布快照详情没有Skill；导入草稿则绑定“fund-chain-investigation 副本 2”。草稿确认已选涉诈规则库、涉诈案例库后，发布隔离测试V2 `V8恢复验收-测试版-20261030`，V2详情含绑定Skill。普通V2只读工单请求再次成功。不要把缺Skill的自动V1当作完整恢复版本。
- 导入默认选GLM模型，已手动选回 `deepseek-ai/DeepSeek-V4.1-Flash`。发布V2核实 model_id=6、max_steps=15、enable_protocol_repair_retry=true；角色、使用要求、示例与V8源版本一致。草稿八个工具均启用，含七个fundtrace业务工具及knowledge_base_search。知识库选择窗口列出涉诈规则库与涉诈案例库；索引ID来自原租户，跨租户迁移仍需重建或重新选择索引。
- 发布前草稿版完成A0209/v1、A0176/v2研判、A0176/v2只读工单、v1→v2重判及A9999异常账户五项回归。均HTTP 200；完整研判调用Skill副本并检索规则库，工单读取只调用get_ticket，重判只调用rejudge。A9999因协议重试调用get_account两次，返回ACCOUNT_NOT_FOUND后停止，没有工单。关键结果符合本地算法。
- 原始SSE位于工作区 `.local-playwright/output/v8-restore-*.txt`，发布V2工单复测为 `v8-restore-v2-get-ticket.txt`。截图仍按用户要求暂停。此为同租户恢复测试，不证明干净租户迁移；记忆能力需在目标Nexent平台单独关闭。

- 已从本ZIP导入独立智能体2：`fundtrace_restore_test_20261030`，展示名“资金链研判-备份恢复测试-1030”。导入向导自动创建V1，本次未另行点击发布。原智能体1保留V5，名称和关键配置与备份一致。
- 重命名冲突时手动填写测试名称。模型步骤默认选择了GLM-4.5-Air，已显式改选原DeepSeek-V4.1-Flash；不能假定导入自动保留模型选择。
- MCP步骤识别fundtrace为已安装，复用原内网地址。Skill冲突选择“安装为新技能”，创建并绑定`fund-chain-investigation 副本`，未覆盖原Skill。实际read_skill_md调用确认加载副本成功，无需修改提示词。
- 角色/约束/示例提示词、max_steps=15、开场白、示例问题、模型名与备份逐字段一致。七个业务工具及knowledge_base_search可用，原两库索引关联保留。
- 在副本调试会话顺序验证A0209/v1、A0176/v2、get_ticket(A0176,v2)、rejudge(v1,v2)、A9999。追链/规则/工单/重判原始JSON逐字段等于本地算法；get_ticket和rejudge分别只调用目标工具；A9999在ACCOUNT_NOT_FOUND后停止，无工单生成。两次完整研判均实际加载Skill副本并检索知识库，最终答复完整且关键事实正确。
- 原始流restore-a0209-stream.txt、restore-a0176-v2-stream.txt、restore-get-ticket-stream.txt、restore-rejudge-stream.txt、restore-a9999-stream.txt及配置核对记录位于工作区.local-playwright/output/，不在此ZIP内。verify_live.py覆盖上述工具结果核验。
- 本次同环境恢复验收通过，复用了已有模型、MCP与知识库；不等于全新服务器/租户迁移通过，不替代尚未通过的五次独立会话稳定性验收。测试智能体和Skill副本暂保留供检查，普通使用仍选择原“涉诈资金链路研判助手”。
