# Nexent 配置备份

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

- 已从本ZIP导入独立智能体2：`fundtrace_restore_test_20261030`，展示名“资金链研判-备份恢复测试-1030”。导入向导自动创建V1，本次未另行点击发布。原智能体1保留V5，名称和关键配置与备份一致。
- 重命名冲突时手动填写测试名称。模型步骤默认选择了GLM-4.5-Air，已显式改选原DeepSeek-V4.1-Flash；不能假定导入自动保留模型选择。
- MCP步骤识别fundtrace为已安装，复用原内网地址。Skill冲突选择“安装为新技能”，创建并绑定`fund-chain-investigation 副本`，未覆盖原Skill。实际read_skill_md调用确认加载副本成功，无需修改提示词。
- 角色/约束/示例提示词、max_steps=15、开场白、示例问题、模型名与备份逐字段一致。七个业务工具及knowledge_base_search可用，原两库索引关联保留。
- 在副本调试会话顺序验证A0209/v1、A0176/v2、get_ticket(A0176,v2)、rejudge(v1,v2)、A9999。追链/规则/工单/重判原始JSON逐字段等于本地算法；get_ticket和rejudge分别只调用目标工具；A9999在ACCOUNT_NOT_FOUND后停止，无工单生成。两次完整研判均实际加载Skill副本并检索知识库，最终答复完整且关键事实正确。
- 原始流restore-a0209-stream.txt、restore-a0176-v2-stream.txt、restore-get-ticket-stream.txt、restore-rejudge-stream.txt、restore-a9999-stream.txt及配置核对记录位于工作区.local-playwright/output/，不在此ZIP内。verify_live.py覆盖上述工具结果核验。
- 本次同环境恢复验收通过，复用了已有模型、MCP与知识库；不等于全新服务器/租户迁移通过，不替代尚未通过的五次独立会话稳定性验收。测试智能体和Skill副本暂保留供检查，普通使用仍选择原“涉诈资金链路研判助手”。
