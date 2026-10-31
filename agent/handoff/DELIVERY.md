# 乙方技术交付包

包名：`fundtrace-agent-v9-20261031.zip`，生成目录为仓库根目录`dist/`。这是V9技术交付候选包，截图、视频和接收确认未齐，不标记为赛事最终提交包。

## 内容与边界

- `mcp_server/`：服务、自检、安装脚本、部署文档及契约/网络检查脚本；排除日志、进程号、缓存及旧dist。
- `core/`：仅运行所需api/store/trace/rules/ruleset/ticket/rejudge模块及fixtures，不包含数据生成器或读取答案的评测脚本。
- `data/`：300账户、2973笔冻结合成交易与dataset_meta、数据说明。
- `Data and Rules/`：枚举与v1/v2规则YAML。
- `agent/`：提示词、三个Skill、编号核验、验收报告、逐次核验JSON、交接脚本；exports只保留最新V9 ZIP与静态/恢复核对JSON。不包含旧配置ZIP和历史截图。
- `kb/`：规则原文与公开案例摘要。嵌套V9 ZIP才是Nexent“导入”应选择的文件，外层技术包不能直接导入Nexent。
- `MANIFEST.json`：每个文件的大小和SHA256，包含打包时Git HEAD与dirty状态；dirty=true表示有未提交交接改动，不冒称某个纯提交快照。

不包含eval答案、甲方评测结果/图、虚拟环境、依赖wheel、浏览器登录状态、原始SSE、模型密钥、云服务器工单或systemd实际配置。演示配图另由甲提供。包内有当前环境内网地址、租户/知识库索引及作者标识，仅作项目内部交接，不直接公开发布。

## 制作与检查

在仓库根目录使用Python 3.11以上执行，无需另装打包依赖：

```powershell
python agent/handoff/build_delivery.py
```

脚本按文件清单打包，检查常见明文凭据形式（不输出匹配值），验证嵌套Skill ZIP和V9包哈希，临时解压全部文件核对清单/路径/哈希及合成数据CSV哈希，编译检查Python源码。包内shell脚本与两份CSV统一为LF换行；CSV字节哈希必须恢复到dataset_meta记录值，仓库原文件不修改。不执行或更改运行中的服务。结果为外层ZIP、`.sha256`与`.verification.json`。常见形式扫描不保证发现一切秘密，接收前仍按内部配置管理。

生成包未提交Git（dist已忽略），脚本和说明由用户commit/push。每次改动需重跑生成新哈希；不得把旧包哈希用于新文件。打包检查不等于在全新机器安装依赖和运行服务成功。

## 接收后的步骤

1. 解压到新的专用目录，先查看根目录MANIFEST.json和`agent/handoff/README.md`，确认合成数据与已知问题。
2. Linux安装Python 3.12及python3-venv，创建虚拟环境并安装依赖：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r mcp_server/requirements.txt
```

3. 部署路径和端口确认后，显式启用real模式（不要直接覆盖仍有使用者的旧服务）：

```bash
MCP_MODE=real bash mcp_server/install_systemd.sh
MCP_MODE=real .venv/bin/python mcp_server/selftest.py http://127.0.0.1:8900/sse
```

需要sudo，默认端口8900；预期8工具19调用PASS。工单目录由运行时生成。详细设置见`mcp_server/SYSTEMD.md`和`UPGRADE_REAL.md`。

4. 在目标Nexent准备模型凭据、Embedding与两个知识库，上传`kb/`中的规则和公开案例并等待索引就绪。注册后端可访问的MCP地址，不照搬原环境内网地址。
5. 导入`agent/exports/fundtrace_agent-v9-v1.2-20261031.zip`并选择独立名称。向导模型默认值可能不同，显式改回目标环境对应的DeepSeek-V4.1-Flash；不能照搬model_id=6。技能冲突时安装独立副本，再核对三个绑定Skill与知识库索引。
6. 检查max_steps=15、协议修复true、平台记忆关闭。导入自动发布版可能缺Skill，必须检查草稿，再发布独立测试版并检查发布详情。
7. 按`agent/handoff/DEMO.md`验证A0209/v1、A0176/v2、只读工单、版本比较和A9999。只有当前租户恢复有验收记录，目标环境须重新测试，不能沿用原成绩。

本包没有承诺零格式错误：恢复验收中一次只读正文遗漏、相同问题两次复测完整，详见`agent/evaluations/v9-restore-20261031.md`。知识库条文不等于账户证据，工具成功也不等于最终答复完整。
