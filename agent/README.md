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

## 当前环境记录（2026-10-29）

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
- 云端服务运行命令（用户已验证的前台方式）：

```bash
cd ~/fundtrace-mcp
MCP_MODE=fixture MCP_HOST=0.0.0.0 MCP_PORT=8900 MCP_TRANSPORT=sse \
  .venv/bin/python mcp_server/server.py
```

- 后台运行、进程守护、开机自启尚未验收，前台服务窗口需保持运行。
- 规则库素材：`kb/rules_v1_draft.md`，规则问答及与 MCP 联合研判已获得文档引用；引用展开与检索调用记录待留档。
- Skill 文件：`agent/skills/fund-chain-investigation.md` 已创建；用户按上传绑定步骤进行测试，实际技能加载记录尚待留档核实。
- 重新导入时需手动配置模型、MCP 地址与权限、规则知识库及向量模型，并确认 Skill 和工具绑定；配置导出/导入尚未验收。

## 注意

- 提示词要求：编号必须来自工具返回，每条结论带交易编号，列出反向证据和缺失证据，只给三种建议动作，不联网。
- 导入配置后需要手动补的资源（MCP 地址、知识库、模型）都要写在本文件里。
