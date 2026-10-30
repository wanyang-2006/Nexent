# 智能体测试记录

## 交接素材整理（2026-10-30）

- 新建agent/handoff/README.md，列明材料路径、工具功能实测、截图索引、演示顺序、证据边界和未完成事项；接收人及日期保留待确认。
- 通过已登录Nexent只读查看原智能体1，补拍7张截图至agent/handoff/screenshots/。工具与Skill图可见7个业务工具和fund-chain-investigation；规则库3文档/7分块、案例库5文档/5分块，两库Embedding均Qwen/Qwen3-Embedding-4B；文件详情全部已就绪。最大步数15，平台记忆能力关闭。
- 已逐张查看并重拍被裁切的工具/文件图。配置首页只覆盖名称和发布版本标签，模型、知识库绑定等截图缺口在交接表明确列出。历史引用展开和r1普通问答图保留原位置，不当作当前V5完整验收证据。
- 本次未运行新问答、未修改业务配置、未发布版本、未重启服务器，未向甲或丙发送消息。材料就绪不等于已完成交接、稳定性或正式v1.0验收。

## 通用编号核验（2026-10-30）

- 新增agent/check_ids.py：编号格式读取权威enums.yaml，账户/交易回查core.store，资金链按指定规则版本回查core.api.trace_chain；不生成或读取工单文件。支持UTF-8/BOM文件、标准输入、JSON报告和仅提取SSE最终答复。
- tests/test_agent_check_ids.py的5项测试通过：可变位数及嵌套编号、真实链的版本区别、未知编号及无编号、SSE排除工具日志、CLI文件与退出码。使用既有_tmp_testdeps补充pytest依赖运行，无新增安装。
- 实际数据集sim-gen_profile_v1-seed42，核验已有5个演示回复及5个重复回复，结果如下。文件均位于工作区.local-playwright/output/；逐文件执行`python agent/check_ids.py <文件> --sse-final --rule-version <版本>`。

| 回复文件 | 版本 | 去重账户/交易/链数 | 编号核验 |
|---|---|---|---|
| r1-a0209-stream.txt | v1 | 7/5/1 | PASS |
| reg-a0044-stream.txt | v1 | 6/5/1 | PASS |
| r2-thinking-a0105-stream.txt | v1 | 9/8/0 | PASS；该轮开启深度思考 |
| reg-a0074-stream.txt | v1 | 9/18/0 | PASS |
| a0176-v2-real-stream.txt | v2 | 4/3/1 | PASS |
| stable-r2-1-stream.txt | v1 | 7/18/1 | PASS |
| stable-r2-2-stream.txt | v1 | 6/5/1 | PASS |
| stable-r2-3-stream.txt | v1 | 6/5/1 | PASS；原答复截断，业务验收仍失败 |
| stable-r2-4-stream.txt | v1 | 1/0/0 | PASS；原答复为DSML文本，未执行工单，业务验收仍失败 |
| stable-r2-5-stream.txt | v1 | 6/18/1 | PASS |
| r2-a9999-stream.txt | v1 | 1/0/0 | FAIL；未知A9999，符合正确拒答预期 |

- 此次仅核验已有答复，没有重新调用Nexent或改变发布配置。编号存在不代表金额/方向/账户关联正确，也不证明答复完整或工具已执行；原先完整答复稳定性3/5的结论保留，按用户要求暂缓处理。
- 通用编号核验完成；正式v1.0、服务器重启和异常退出恢复证据仍未完成。

## 同环境备份恢复验收（2026-10-30）

- 用户恢复工作后，从agent/exports/fundtrace_agent-20261030-r2.zip通过Nexent导入向导建立独立智能体2，变量fundtrace_restore_test_20261030，显示“资金链研判-备份恢复测试-1030”。导入自动创建V1，未额外点击发布。模型手动选原DeepSeek，MCP复用已安装fundtrace，技能按新副本导入，原智能体/技能未覆盖。
- 配置比较通过：三块提示词、最大步数15、开场白、示例问题、模型名与ZIP相同；七个业务工具和知识库检索可用。检查原智能体1仍为current_version_no=5，名称和上述关键配置与备份相同。
- 调试会话依次完成A0209/v1（REVIEW、中转端、L-T01908）、A0176/v2（REVIEW、一级收款端、L-T01338）、只读get_ticket、300户/8升级/0降级rejudge、A9999。两个完整流程都实际加载fund-chain-investigation 副本并检索知识库；追链/规则/工单与本地逐字段一致。读取和比较分别只有get_ticket/rejudge调用；不存在账户仅Skill和get_account调用后停止，未生成工单。最终答复完整，链边方向及反向/缺失证据正确。
- 验证脚本verify_live.py和原始restore-前缀SSE、导入配置快照存于工作区.local-playwright/output/。同环境配置导出/导入恢复验收通过；复用现有知识库、模型、MCP，不代表异环境迁移验收，也不是五个独立会话稳定性复测。旧3/5稳定性结果保留，用户已要求暂时搁置。
- 测试副本和Skill副本保留；下一项为agent/check_ids.py通用编号核验及交接材料。未提交推送，未执行服务器重启或异常恢复操作。


## 智能体配置导出（2026-10-30）

- Nexent「我的智能体 → 更多操作 → 导出」成功，下载ZIP已归档agent/exports/fundtrace_agent-20261030-r2.zip，校验值及迁移说明见agent/exports/README.md。
- 静态核对agent.json及内嵌Skill：七个MCP工具、knowledge_base_search、两个索引关联、提示词、模型名、max_steps=15及MCP地址存在。导出不包含知识库正文、模型凭据、服务代码/数据或systemd；跨环境需要重新关联资源。
- 未执行导入恢复，配置导出导入整项尚未验收完成；没有创建额外智能体、覆盖原配置或修改协议修复设置。


## systemd恢复检查回传（2026-10-30）

- 用户在服务器重启验收步骤后回传：is-enabled=enabled、is-active=active。首次未指定MCP_MODE的网络自检返回AssertionError；显式执行MCP_MODE=real后，返回PASS: 8 tools; 19 MCP calls; real algorithms on synthetic dataset，服务及real模式协议检查通过，无需重装。
- 上述状态与自检来自用户终端输出。尚未提供本次开机时间、启动日志或明确重启完成记录，因此严格的重启自动恢复证据待补；进程异常退出恢复也未实测。自检命令须显式指定MCP_MODE=real，避免按默认模式断言。


## V5补充回归与稳定性实测（2026-10-30）

此段为最新状态，优先于下方历史记录。限流恢复后发现DSML调用标签被当作最终文本，非MCP业务错误。

- V4普通A0105：画像/流水/追链/规则成功，随后输出DSML知识库调用标签，未真正检索、未生成工单；同会话补充指令仍输出标签，不计通过。原始流reg-a0105-resume-stream.txt、reg-a0105-recover-stream.txt。
- 草稿补充Python CodeAgent执行协议后，A0105完成Skill、知识库、make_ticket；追链/规则/工单与本地逐字段一致。沿用用户已授权的发布操作，发布Nexent V5，名fundtrace-全算法合成数据-20261030-r2。request.version_no=5已核实。此版本仍为联调版，未通过稳定性验收，不代表正式v1.0。
- V5普通A0074/v1通过：INSUFFICIENT、无链路/角色、风险R02和反向R10、TK-v1-A0074；正确说明流水仅返回200/228笔，保留3项缺失证据和建议补充材料。原始追链/规则/工单与本地一致。
- V5普通A0105/v1通过：CLEAR、无链路/角色、R09及工资T01736/A0162转入8094元、两项缺失证据。该轮在会话模型菜单开启深度思考，request记录deep_thinking=true/thinking_effort=low；不将其混入默认参数稳定性统计。草稿和普通原始流分别为draft-code-a0105-stream.txt、r2-thinking-a0105-stream.txt。
- V5普通A0176/v1首轮DSML失败，无make_ticket。开启深度思考的草稿重试取得完整正确工具结果，但正文把“开户距数据起始日16天”误写成“开户16天后出现大额转入”，不记为无措辞问题。随后默认参数普通新会话重试通过：RISK_SIGNAL、无链路/角色、R04/R05/R08、TK-v1-A0176、三项缺失证据；开户16天口径正确。证据reg-a0176-v1-stream.txt、draft-thinking-a0176-stream.txt、r2-a0176-retry-stream.txt。
- V5普通A9999通过：只调用read_skill_md和get_account，实际返回ACCOUNT_NOT_FOUND后停止；无流水/追链/规则/工单调用，最终明确未生成工单。证据r2-a9999-stream.txt。

### A0209/v1五个独立普通会话

全部使用同一提示词、V5、model_id=6、generation_config.deep_thinking=false，history=[]，is_debug=false；未改变发布配置。模型菜单深度思考在新会话重置，不默认继承上一会话设置。

| 轮次 | 工具原始结果 | 最终答复 | 结论 |
|---|---|---|---|
| 1 | 追链/规则/工单逐字段等于本地，Skill/KB成功 | 状态/角色/链/5条边/4规则/反向与4项缺失证据正确 | 通过 |
| 2 | 同上 | 同上 | 通过 |
| 3 | 同上 | 正文在反向证据段中途截断，缺少缺失证据 | 不通过 |
| 4 | 追链/规则成功，未真正执行make_ticket | 最终为DSML工单调用标签 | 不通过 |
| 5 | 追链/规则/工单逐字段等于本地，Skill/KB成功 | 状态/角色/链/5条边/4规则/反向与4项缺失证据正确 | 通过 |

结论：完整答复3/5，本批稳定性验收未通过。不能删除失败轮次或把成功工具结果当作完整答复成功；3/5仅为本批样本结果，不能推广为模型准确率。各轮没有search_memory调用。原始响应stable-r2-1至5-stream.txt、请求stable-r2-1至5-request.json保存在工作区.local-playwright/output/；verify_live.py保留逐字段断言及失败原因。

下一步应修复模型/平台输出格式兼容性及截断原因，再以冻结配置重新执行五次验收。仅加提示词未解决，单次开启深度思考成功也不能证明已修复。MCP无需重新部署；未执行服务器重启演练、配置导入导出或提交推送。

## 补充账户回归（2026-10-30）

- 发布版V4独立新会话A0044/v1通过：TK-v1-A0044、RISK_SIGNAL/存在风险信号、疑似受骗付款端、L-T01908、R07与本地一致。五条链边方向正确，反向证据为空的边界及合成数据声明正确；原始追链/规则/工单JSON经verify_live.py逐字段比较通过，记录Skill及知识库调用。
- 证据：工作区.local-playwright/output/reg-a0044-stream.txt、reg-a0044.yml，不在仓库内。
- A0105/v1首轮未完成：Skill加载后模型请求持续重试，最终返回model_rate_limit_exhausted（模型请求过于频繁），无最终研判，不计通过。原始流reg-a0105-stream.txt保留；不据此判断业务算法失败。
- A0105/v1独立新会话重试仍失败，原始流reg-a0105-retry-stream.txt同样返回model_rate_limit_exhausted，无最终研判。两轮均保留模型和提示词，未改发布版配置；暂缓继续发送回归请求，避免在限流期间累积无效样本。
- A0105、A0074、A0176/v1、A9999及五次独立会话稳定性尚待模型调用恢复后完成，不能标记为稳定性通过。未进行服务器重启演练。

## 发布版普通问答回归（2026-10-30）

- 已按用户授权发布初版；普通问答A0209返回正确事实，但出现DISPLAY:markdown包装和重复正文。补充最终输出格式约束后发布r1，当前为Nexent V4，名称fundtrace-全算法合成数据-20261030-r1。请求体version_no=4已独立确认。
- r1普通问答A0209：新会话完成Skill加载、业务工具、规则检索和工单生成，TK-v1-A0209/REVIEW/L-T01908、五条边和规则结果正确；源头金额口径及counter为空边界已修正，最终正文无DISPLAY包装。原始SSE中的追链/规则/工单JSON逐字段等于本地算法输出。
- r1普通问答rejudge：新会话返回300户、8变化/8升级/0降级；全部变化账户、状态、角色、规则变化及链号与本地rejudge逐字段一致。只调用一个业务工具rejudge，另有平台自动search_memory调用；不把这轮写成记忆关闭验收。最终答复中“无规则移除，因此未降级”的因果解释超出工具字段，数据本身正确，后续稳定性测试需继续约束此类因果归纳。
- 原始流r1-a0209-stream.txt、r1-rejudge-stream.txt及请求r1-rejudge-request.json、页面快照和r1-a0209-published.png保存在工作区.local-playwright/output/。verify_live.py覆盖三轮单账户原始结果、发布版重判与get_ticket调用范围，结果见脚本输出。
- 记忆能力最初开启，自动审批要求补充持久设置授权后未绕过。用户明确回复“允许关闭记忆能力”，随后已关闭开关并保存memory-disabled.yml/png。关闭后的独立普通会话原始流memory-off-rejudge-stream.txt只含rejudge调用，无search_memory；结果与本地300户重判逐字段一致。记忆关闭本轮验收通过。
- 基础发布联调通过，不等于开发乙清单全部完成：仍需服务器重启恢复演练、5次稳定性测试、其余演示账户及异常输入回归、独立编号核验脚本和导出导入验收。

## 全算法云端升级与 Nexent 草稿验收（2026-10-30）

- 用户回传安装结果：两轮 `PASS: 8 tools; 19 MCP calls; real algorithms on synthetic dataset`，服务 enabled、active，确认已完成显式real安装；此项替代下方早前SSH阻塞和hybrid线上状态记录。
- Nexent刷新工具列表成功，保留七个业务工具及两知识库；在线编辑SKILL.md，替换为仓库全算法版，保存成功。更新使用要求、示例和开场白；导航重新打开后显示新版引导，确认草稿持久化。
- 新会话A0209/v1：成功加载read_skill_md；调用画像、流水、追链、规则、知识库检索、make_ticket。返回TK-v1-A0209、REVIEW、中转端、L-T01908，R01/R04/R07/R08；五条边T01908/T01913/T01932/T01938/T01942方向、时间、金额均正确，流入分支未串成不存在的路径。52分钟总跨度和10分钟账户停留已区分。
- 初轮措辞问题：把total_amount称作金额合计，并把counter为空延伸为无正常经营特征；已补充提示词明确源头汇入规模和反向证据边界。最终提示词保存在agent/prompt_real.md。
- 新会话rejudge(v1,v2)：直接调用rejudge，覆盖300户、变化8户、升级8户、降级0户，名单A0015/A0039/A0104/A0127/A0146/A0168/A0176/A0261与本地一致。未执行单账户流程。快照rejudge-real-live.yml；该轮原始流未保存，后续普通问答复测补充。
- 新会话A0176/v2：TK-v2-A0176、REVIEW、一级收款端、L-T01338，命中R01/R04/R05/R08/R11。T01338/T01349汇入、T01381汇出，85105源头金额、82445转出；counter为空且未推断无真实业务，四项缺失证据和v2规则引用齐全。回复六个标题，五项内容均覆盖，建议动作另列。
- 新会话get_ticket(A0176,v2)：只调用get_ticket，返回与刚生成工单一致，未重新研判、未出现NameError，包含real模式标记。
- 已通过浏览器网络记录保存A0209、A0176和get_ticket的原始SSE响应；其中execution_logs包含实际工具JSON输出，不仅是模型自述。工作区.local-playwright/verify_live.py从前两轮流提取结果，与本地core.api逐字段比较追链/规则/工单，全部通过；同时断言real标记、read_skill_md和knowledge_base_search调用存在，工单写入临时目录。
- 原始流和快照保存在工作区.local-playwright/output/，不在仓库内；包含内部调试内容，仅作联调留档。
- 用户明确授权“发布新版本并验证普通问答”；已发布命名fundtrace-全算法合成数据-20261030，普通开始问答已显示新版开场白，发布后回归另记。

## Playwright 云端实测（2026-10-30）

- 已通过 Playwright MCP 登录并检查 Nexent 智能体 1 的草稿；页面显示已发布 V2，当前发布名为涉诈资金链路研判助手-2610292041。以下对话在草稿调试区执行，不能视为已发布版本验收；本次没有修改或发布线上配置。
- 绑定检查：七个 fundtrace 业务工具（含 get_ticket、rejudge）、fund-chain-investigation 技能、涉诈规则库与涉诈案例库均已选择；最大步数15。案例库5文档/5分块，规则库3文档/7分块。本次未核实记忆开关。
- A0209/v1 完整研判未通过：页面出现 read_skill_md 调用及四个查询/分析调用记录，随后出现 make_ticket 调用记录；trace_chain 展开的参数为 A0209/max_hops=4/v1。最终答复报告画像/流水成功（15笔），追链、规则、工单返回 ACCOUNT_NOT_FOUND，未生成工单，也未返回 L-T01908。当前记录面板只展示参数，未展示原始工具响应，因此错误值来自模型最终答复，不能充作独立原始响应日志。现象符合昨日 hybrid：查询完整合成数据，分析仍为固定样例。
- 仅知识库问答通过内容核对：检索涉诈规则库和涉诈案例库，回答 R01 v1=60分钟、v2=120分钟、金额>=10000、比例0.9至1.1，与本地生成规则一致；案例01提供最高检来源及报道摘要，区分公开报道事实与作品规则解读。最终显示6个来源，点击规则v2引用成功打开来源面板，可查看rules_v2、rules_v1、diff和案例摘要。未访问外部报道网站；最高法备用链接在最终回复中错误拼入引用标记，需后续修正链接格式。
- rejudge 对话工具调用成功出现，最终返回 total=10、changed=3、upgraded=3、downgraded=0、mode=fixture，变化账户A0044/A0123/A0176；明确标注样例覆盖范围。旧的NameError问题本轮未复现。全算法预期300户/8升级尚未达到；本轮不是独立新会话，切换real后仍须新会话回归。
- 原始页面快照及引用截图保存在工作区 `.local-playwright/output/`（不在仓库内）：a0209-hybrid-evidence.yml、kb-live-evidence.yml、rules-citation-evidence.yml、rejudge-live-evidence.yml、knowledge-citations.png。快照包含调试区内容，按内部联调材料管理。
- 阻塞：本机SSH非交互认证失败（publickey,password）；用户表示已在自己的SSH终端登录，该终端会话不能由独立SSH命令复用。需在用户远程终端完成最新部署包上传/安装，云端real协议自检通过后，再同步线上提示词/Skill及会话引导。当前云端尚不记为real验收通过。

## 恢复与全算法本地验收（2026-10-30）

- 仓库基线 HEAD `7cdfab6`：core.api 六个核心函数已全部实现，规则与公开案例更新。保留现有 staged requirements.txt 修改，未提交、未推送。
- 将 pytest 安装到工作区忽略的 `_tmp_testdeps`，使用 Python 3.12.14/FastMCP 4.1.4 执行 `python -m pytest tests -q`：81 passed。9项MCP契约测试通过，包含真实引擎工单生成/配置目录读取、300账户重判及错误不回退。
- fixture/hybrid/real 三模式各自通过 SSE、Streamable HTTP 网络测试。fixture/hybrid 每轮18次调用；real 每轮19次，包含 A0044范围交易、A0176 v1 RISK_SIGNAL/v2 REVIEW、300账户重判及无效输入。
- 已更新全算法部署包清单，纳入 trace/rules/ruleset/ticket/rejudge、枚举和两版规则，新增PyYAML依赖；归档不含eval、答案、生成脚本、预生成工单。新版包已生成；云端/Nexent仍以昨日hybrid验收为最后已知状态。
- 最新操作文档 `mcp_server/UPGRADE_REAL.md`；必须显式选择 real 后再更新线上提示词/Skill并验收。real 指实际计算合成数据，不是真实银行数据。

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
