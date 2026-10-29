# 智能体测试记录

日期：2026-10-29。当前后端为 fixture。提示词版本号为本记录按会话迭代编排的标签，不是 Nexent 已发布版本号。
导出回复保存在用户 Downloads 目录，尚未复制归档；本表不把最终回复中的执行自述当作独立调用日志。

| 测试/迭代 | 输入/对象 | 观察与结果 | 证据 | 需补的验收 |
|---|---|---|---|---|
| MCP 云端部署 | 进程内及 http://127.0.0.1:8900/sse 自检 | 两次均 PASS: 8 tools; 18 MCP calls including filtering and invalid inputs | 用户粘贴的终端输出 | 后台运行/重启验收 |
| Nexent 注册 | fundtrace | 页面显示连接成功、已启用、8个工具 | 用户截图 | 项目内截图归档 |
| 提示词p0：基础研判 | A0087 | 样例和工单内容基本正确；错误串接并列汇入；开户措辞矛盾；无依据断言工资与转账无关 | message-1793266147384.md | 已用后续提示词修正 |
| 提示词p1：证据约束 | A0087 | 并列汇入、开户描述及工资关联边界修正；曾误把43/47分钟视为数据矛盾 | message-1793266623042.md | 后续已澄清起算点不同 |
| 规则库问答 | v1 R01 条件与来源 | 窗口60分钟、金额≥10000、比例0.9至1.1、文档引用及仿真声明正确 | message-1793268698432.md | 点击引用和检索记录截图 |
| MCP与知识库联合研判 | A0087，解释R01并生成工单 | 规则引用、交易编号、真实edges关系、反向证据与工单一致 | message-1793268937801.md | MCP/知识库执行日志归档 |
| Skill配置后研判 | A0087，解释R01并生成工单 | 五项输出格式正确；43分钟停留与47分钟跨度解释正确；未发现样例数字或链边编造 | message-1793269538685.md | 核对实际Skill加载记录，不仅看最终文字 |
| 异常账户 | A9999，并生成工单 | 回复报告ACCOUNT_NOT_FOUND，明确只表示样例集不支持；未返回A0087画像，未声称生成工单或认定无风险 | message-1793269751783.md | 调用日志确认失败后没有继续调用其他业务工具 |

后续真实接口接入后，新加测试记录并明确模式、数据版本与提示词/发布版本；本表不作为真实数据研判效果或准确率评测。

## 仓库更新后的查询 API smoke test（2026-10-29）

HEAD 0ccfce8 新增 core.store 与 core.api 的账户、交易查询实现。使用本机 Python 3.12 调用：A0087/A0044账户查询返回 data/ 中完整数据；A0044 在 2026-03-05 闭区间筛选返回 T01908、T02136；A9999 返回 ACCOUNT_NOT_FOUND；limit=201 返回 BAD_PARAM。直接 smoke test 通过。完整 tests/test_api_queries.py 未运行，因为当前测试环境没有 pytest。

该代码没有加入当前云端 systemd 运行的服务，MCP 仍为 fixture 模式。真实接入前需先实现逐工具混合路由；core.api 目前只实现 get_account/get_transactions。

## Hybrid MCP 本地验收（2026-10-29）

实现 `MCP_MODE=hybrid` 后运行 `mcp_server/test_contract.py -v`：8项通过，包括完整合成数据查询、其余工具仍返回 fixture、查询错误不回退。`MCP_MODE=hybrid python mcp_server/selftest.py --in-process`：8工具18次调用通过。`mcp_server/test_network.py`：fixture/hybrid 各自通过 SSE 与 Streamable HTTP 网络协议及工单隔离检查。

部署状态：已生成并核对 `mcp_server/dist/fundtrace_mcp.tar.gz`，包含 core、fixtures、三份 data 文件，不含 eval。修正了 Windows pip 将 pywin32 混入 Linux 依赖下载的问题，更新包不捆绑依赖，沿用云端现有 FastMCP 虚拟环境。用户粘贴的 ECS 安装输出显示两轮 8 工具/18 次调用自检通过，systemd 已 enabled、active；安装脚本的 SSE 自检显式按 hybrid 断言。Nexent 刷新 MCP、A0044 hybrid 查询及智能体端验收待完成。pytest 依赖不可用，tests/test_api_queries.py 全套尚未验证。

## ECS 与 Nexent hybrid 验收（2026-10-29）

- 用户提供的云端 systemd 安装输出：安装脚本两轮 `PASS: 8 tools; 18 MCP calls`，服务 `enabled`、`active`。
- Nexent 直接工具测试：`get_account(A0044)` 返回 `synthetic_dataset`、数据集 `sim-gen_profile_v1-seed42`；`get_transactions(A0044, limit=2)` 返回 `total=22`、`count=2`、`truncated=true`；`trace_chain(A0087,v1,max_hops=4)` 返回带 `fixture` 的固定样例。三项均符合预期。
- 智能体对话 `message-1793281588375.md`：A0044 画像中的账户信息、交易计数/金额、对手方数量、首末交易时间与 MCP 输出一致；声明合成数据、非真实银行数据，并明确不能将 A0087 样例工具拼成 A0044 的研判。账户画像对话验收通过。
- 智能体对话 `message-1793281780690.md`：查询 A0044 在 2026-03-01 11:00 至 2026-03-02 00:00、limit=5，回复列出 T00121、T00224、T00365，金额17、403、1639元。用本地同版本 core.api 独立查询确认 total=3、count=3、truncated=false，编号、时间、账户方向和金额一致；汇总转出2笔420元、转入1笔1639元、净流入1219元及3个对手方均正确。正确标注合成数据并声明未调用其他分析工具。交易明细对话内容验收通过；Nexent 实际调用日志未提供，工具调用属回复陈述。
- 剩余限制：追链、规则、工单、重判算法接口仍未接入全量数据；不得据此声称 A0044 完整研判已完成。

## 暂停点（2026-10-29）

用户要求暂停并记住进度。恢复后的第一项：在 Nexent 验收规则知识库 R01，检查规则 v1 的触发条件、窗口、判断口径与 `kb/rules_v1.md` 一致，确认引用链接可打开及检索记录命中文档。第二项：做 A0087 规则库 + MCP 联合研判。随后再核实 Skill 加载记录和其他清单项。Hybrid MCP 已部署且服务 active；A0044 画像/流水对话内容验收通过，不需重复部署。完整 A0044 算法研判及 pytest 全量测试仍未完成。

## 暂停时待测试项（2026-10-29）

最新直接测试：用户通过 Nexent 工具测试分别返回完整 JSON，两项均通过。

- get_ticket(A0087,v1)：返回 TK-v1-A0087、REVIEW、一级收款端、L-T00412，支持/反向/缺失证据齐全，含 _demo.mode=fixture；source=make_ticket.json 是当前样例包装的预期行为，不表示调用失败。
- rejudge(v1,v2)：返回 total=10、changed=3、upgraded=3、downgraded=0，变化账户 A0044、A0123、A0176，含 _demo 标记，与已有 fixture 一致。
- 因此当前这两项 MCP 工具的直接访问及样例能力已确认；之前对话测试仍未通过，不能用直接测试覆盖为对话已通过。下一步调整按意图直接调用的指令，保存并确认草稿/发布版本后，分别新开对话复测，检查实际成功调用记录。NameError 后声称成功的问题仍需回归。

后续收到两个工具的首次对话测试，均未通过：

- message-1793276815113.md：get_ticket 调用显示 NameError: name 'get_ticket' is not defined，随后仍输出“工单已生成”和详细样例。没有成功调用证据，不能认定读取成功；需核实智能体工具绑定、工具刷新及实际执行记录，禁止在调用失败后用历史上下文声称成功。
- message-1793276926865.md：版本比较回复引用“现有 fixture 只提供 v1 结果”的 BAD_PARAM，进而宣称 v2 重判不支持。该错误文字对应带 rule_version 的单账户工具，当前 rejudge(old=v1,new=v2) 应有独立固定样例。需直接测试 rejudge 并核实实际工具名/参数，不能将单账户v2限制泛化为重判样例不可用。导出回复还含内部执行提示文字。
- 下一步：核实 get_ticket/rejudge 已绑定并保存，分别做工具卡片直接测试；直接测试通过后刷新并新开对话，优先按请求调用指定工具，不运行完整单账户研判或额外v2查询。当前两项均保持未通过。

后续部署恢复记录：用户发现8900无监听且连接失败，nohup重启后恢复；于2026-10-29 20:18 CST安装systemd，旧nohup进程已停止。安装输出包含两次8工具18调用自检通过，systemctl显示enabled、active (running)。确认配置和当前运行正常；服务器重启、异常退出自动恢复演练及本次更换进程后Nexent重新问答未留档。

已提供 get_ticket/rejudge 的绑定步骤、提示词补充和测试问题，尚未收到实际执行结果，不记为测试通过。恢复后先核实绑定，再分别新开会话测试 A0087/v1 工单读取、v1到v2固定样例比较（10账户中3个变化）。
