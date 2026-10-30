# 2026-10-30 全算法模式升级

适用仓库基线：`7cdfab6` 及本次乙方 MCP 配套修改。云端上次验收仍为 hybrid；本地通过不等于线上已更新。

## 本次变化

- `core.api` 六个核心函数已实现；MCP 的 `get_ticket` 从 `FUNDTRACE_TICKET_DIR`（默认 `tickets/`）读取工单，缺失时调用 `make_ticket`。旧缓存工单需用 `make_ticket` 明确重新生成。
- `MCP_MODE=real` 时七个业务工具均执行算法，返回 `_demo.mode=synthetic_dataset`、`backend_mode=real`、数据集编号。数据仍为300账户、2973笔合成交易，不是真实银行记录。
- fixture/hybrid 模式仍可用。安装脚本默认保持 hybrid，只有显式传入 real 才切换。
- 新 API 现在依赖完整算法模块、规则 YAML 与枚举；即使保留 hybrid，也必须一起部署这些文件。打包脚本已纳入它们。不打包 `eval/`、答案、预生成工单或生成脚本。
- 历史 A0087 工单、10账户/3变化样例仅适用于 fixture。全算法模式不得据此验收，也不得沿用“只支持 A0087”的智能体提示词。

## 1. 本机制作和上传更新包

在 Windows PowerShell 执行，SSH连接名使用 VS Code Remote SSH 的 Host 别名：

```powershell
powershell -ExecutionPolicy Bypass -File "D:\ICT开发者乙任务\GithubClone\Nexent\mcp_server\pack_for_ecs.ps1" -PyVersion 3.12 -Arch x86_64 -PythonExe "C:\Users\K3559\Documents\Codex\2026-10-29\mcp\.venv\Scripts\python.exe"
scp "D:\ICT开发者乙任务\GithubClone\Nexent\mcp_server\dist\fundtrace_mcp.tar.gz" 你的SSH连接名:~/fundtrace_mcp.tar.gz
```

包不包含 Python 依赖，不需要 Windows 跨平台下载 Linux wheel。

## 2. 云端备份并升级

在远程终端执行。备份保留当前代码、数据、规则和工单，不打包虚拟环境：

```bash
cd ~/fundtrace-mcp
tar -czf ~/fundtrace-before-real-$(date +%Y%m%d-%H%M%S).tar.gz mcp_server core data
tar -xzf ~/fundtrace_mcp.tar.gz --strip-components=1 -C ~/fundtrace-mcp
.venv/bin/python -m pip install -r mcp_server/requirements.txt
MCP_MODE=real bash mcp_server/install_systemd.sh
sudo systemctl status fundtrace-mcp --no-pager
MCP_MODE=real .venv/bin/python mcp_server/selftest.py http://127.0.0.1:8900/sse
```

预期两轮安装自检均显示 `PASS: 8 tools; 19 MCP calls; real algorithms on synthetic dataset`，服务 enabled、active。不要同时启动 nohup。失败时检查 journal；回到 hybrid 可执行 `MCP_MODE=hybrid bash mcp_server/install_systemd.sh`，但这只切换路由，不还原代码与数据。若已有 systemd drop-in 覆盖 MCP_MODE，需要同时核对 `sudo systemctl cat fundtrace-mcp`。

## 3. Nexent 工具与提示词

刷新 fundtrace 工具说明，确认智能体绑定七个业务工具。URL仍沿用当前可用地址。

把智能体原有“只支持 A0087/v1”“全部是固定样例”等限制替换为以下约束。仅在云端 real 自检通过后应用：

> 当前 fundtrace 已接入全量合成数据算法。先以实际工具返回的 _demo 为准：synthetic_dataset/backend_mode=real 表示对合成数据实际计算，绝非真实银行记录；fixture 表示固定样例，不能混用。单账户研判使用同一账户、同一规则版本调用工具；默认 v1，用户指定 v2 时按 v2 查询、追链、核对规则并生成工单。版本比较直接调用 rejudge(old,new)，其 summary.total 为实际覆盖账户数，不预填10或3。读取工单用 get_ticket；需刷新已有工单时用 make_ticket。工具错误必须如实报告，不从历史回复补造结果。规则知识库只解释规则，不提供账户交易证据。

同步更新已绑定的 `agent/skills/fund-chain-investigation.md`，新开对话，避免旧样例上下文影响结果。

## 4. Nexent 验收顺序

1. `check_rules`：`{"acct_id":"A0176","rule_version":"v2"}`，应返回该账户规则及数据集标记。
2. `make_ticket`：同样参数。v2 应为 REVIEW；v1 应为 RISK_SIGNAL。工单和证据编号以实际数据为准。
3. `get_ticket`：同样参数，核对与刚生成的工单一致。
4. `rejudge`：`{"old":"v1","new":"v2"}`，应覆盖300账户，变化名单含 A0176。不要套用旧的3账户样例名单。
5. 智能体新开对话：请按 v2 研判 A0176，结合规则知识库说明依据并生成工单；结果应有合成数据说明、支持/反向/缺失证据、版本一致的规则引用。

## 5. 知识库更新

“涉诈规则库”上传 `kb/rules_v1.md`、`kb/rules_v2.md`、`kb/rules_diff_v1_v2.md`，将原草稿停用或移除后再检索，避免旧文档冲突。

“涉诈案例库”使用当前 `kb/cases/` 的5篇公开报道摘要。案例02为网络赌博上游，案例03为涉黑受贿上游，不统一称作电信诈骗案例。规则对应是作品解读，公开报道不能证明仿真阈值。云端上传与引用可打开情况仍需实际验收。
