# mcp_server/

2026-10-31：云端已验收 `MCP_MODE=real`，8工具/19次协议调用通过，systemd开机恢复及异常退出恢复均已有实测记录。七个业务工具执行完整算法，数据为300账户、2973笔合成交易，不是真实银行数据。当前V9交接与验收边界见 [交接首页](../agent/handoff/README.md)。部署升级见 [UPGRADE_REAL.md](UPGRADE_REAL.md)，服务管理见 [SYSTEMD.md](SYSTEMD.md)。

以下保留早期fixture/hybrid操作记录；其中模式状态不代表当前已部署状态。新部署必须显式选择real并使用升级文档的完整文件清单。

MCP 服务目录，由乙维护。把甲的 6 个核心函数加上 `get_ticket` 包装成 MCP 工具，供 Nexent 智能体调用。

更新日期：2026-10-29。本文是中文配置入口；当前代码默认运行固定仿真样例模式。

仓库已加入混合模式：`MCP_MODE=hybrid` 时，`get_account` 和 `get_transactions` 查询 `data/` 中的 300 个账户、2973 笔合成交易；其余追链、规则、工单、重判工具仍返回固定 fixture。查询结果带有 `_demo.mode=synthetic_dataset` 和数据集编号，绝非真实银行数据。禁止把其他账户的查询结果与 A0087 fixture 分析拼接。云端已安装的服务不会因本地仓库更新而改变，需在新版包部署后再按 [SYSTEMD.md](SYSTEMD.md) 更新。

开机自动启动、进程退出自动重启：见 [SYSTEMD.md](SYSTEMD.md)，安装脚本为 `install_systemd.sh`。安装前确认并停止旧 nohup 进程，避免端口冲突。

## 一、先确认部署位置

下面的 Linux 命令在 VS Code 的**远程终端**执行，目标是 Nexent 所在的云服务器。
Windows 文件路径仅用于本机上传文件，不能在服务器终端直接使用。

云端需要同时存在以下目录，不能只上传 `server.py`：

```text
fundtrace-mcp/
├── mcp_server/
│   ├── server.py
│   ├── selftest.py
│   ├── requirements.txt
│   └── README.md
├── core/
│   ├── api.py
│   ├── store.py
│   └── fixtures/
│       ├── get_account.json
│       ├── get_transactions.json
│       ├── trace_chain.json
│       ├── check_rules.json
│       ├── make_ticket.json
│       ├── rejudge.json
│       └── error.json
└── data/
    ├── accounts.csv
    ├── transactions.csv
    └── dataset_meta.json
```

如果服务器上已有最新完整仓库，直接进入仓库根目录即可，不必再次上传。
如果使用部署包，先在远程终端执行 `mkdir -p ~/fundtrace-mcp`，再从本机上传完整 zip。
例如，在本机 PowerShell 执行，替换部署包路径和 SSH Host 名称：

```powershell
scp "D:\ICT开发者乙任务\fundtrace-fixture-20261029-v2.zip" 你的SSH连接名:~/fundtrace-mcp/
```

SSH 连接名使用 VS Code 远程连接时选择的 Host 名称，以沿用 SSH 端口和密钥配置。
随后回到远程终端解压：

```bash
cd ~/fundtrace-mcp
python3 -m zipfile -e fundtrace-fixture-20261029-v2.zip .
ls mcp_server core/fixtures
```

## 二、安装与自检

以下命令都在服务器上的项目根目录执行，即同时含有 `mcp_server/` 和 `core/` 的目录。
Python 需要 3.10 或以上；本次实际测试使用 Python 3.12、FastMCP 4.1.4。

```bash
python3 --version
python3 -m venv .venv
.venv/bin/python -m pip install -r mcp_server/requirements.txt
MCP_MODE=hybrid .venv/bin/python mcp_server/selftest.py --in-process
```

预期结果：

```text
PASS: 8 tools; 18 MCP calls including filtering and invalid inputs
```

这一步验证工具本身，尚未证明 Nexent 容器能访问服务。
如果任何命令报错，先解决该错误，再执行下一步。

## 三、启动 SSE 服务

先以前台方式启动，便于直接查看日志：

```bash
MCP_MODE=hybrid MCP_HOST=0.0.0.0 MCP_PORT=8900 MCP_TRANSPORT=sse \
  .venv/bin/python mcp_server/server.py
```

保持该终端运行。另开一个远程终端，进入同一项目目录，执行网络自检：

```bash
.venv/bin/python mcp_server/selftest.py http://127.0.0.1:8900/sse
```

同样应显示 8 个工具、18 次调用通过。自检会生成带 `_demo` 标记的样例工单。
确认通过后，可在前台窗口按 Ctrl+C 停止，再启动后台服务：

```bash
nohup env MCP_MODE=hybrid MCP_HOST=0.0.0.0 MCP_PORT=8900 MCP_TRANSPORT=sse \
  .venv/bin/python mcp_server/server.py > mcp.log 2>&1 < /dev/null &
echo $! > mcp.pid
tail -n 30 mcp.log
```

`nohup` 用于断开 SSH 后继续运行，不提供服务器重启后的自动启动；长期运行可接入现有进程管理服务。
重新部署代码后需要重启 MCP，并刷新 Nexent 工具列表。

## 四、在 Nexent 填写配置

入口：MCP 仓库 → 我的 MCP → 添加 MCP 服务。也可在智能体的工具选择中进入 MCP 配置。

| 字段 | 当前样例部署填写值 |
|---|---|
| 服务名称 | `fundtrace` |
| 集成类型 | 远程 |
| 传输方式（界面若提供） | SSE |
| 服务 URL | `http://服务器内网IP:8900/sse` |
| Authorization Token | 留空；当前代码没有配置认证 |
| 自定义请求头 | 留空；若界面要求 JSON 对象，填 `{}` |

这里的 IP 必须是 Nexent **后端**能访问的云服务器地址。Nexent 在容器里时，
`127.0.0.1`/`localhost` 指向容器自身，不能直接代表宿主机 MCP。
不要把电脑本机测试的 `127.0.0.1:8901` 填给云端 Nexent。
服务只对需要的内网或 Docker 网段放行 8900，不需要向整个公网开放。

先做连通性校验，再保存。在智能体工具配置中选择 `fundtrace`，刷新并勾选所需业务工具。
如果只能看到 `hello`，说明仍连接到旧版服务；检查服务进程、实际 URL 和工具列表缓存。

## 五、工具测试参数

| 工具 | 测试参数 | 样例能力 |
|---|---|---|
| `hello` | `{"name":"test"}` | 返回 `hello test` |
| `get_account` | `{"acct_id":"A0087"}` | 账户画像 |
| `get_transactions` | `{"acct_id":"A0087","limit":2}` | total=4、count=2、truncated=true |
| `trace_chain` | `{"acct_id":"A0087","max_hops":4,"rule_version":"v1"}` | 资金链样例 |
| `check_rules` | `{"acct_id":"A0087","rule_version":"v1"}` | 风险规则和反向证据 |
| `make_ticket` | `{"acct_id":"A0087","rule_version":"v1"}` | 返回并保存样例工单 |
| `get_ticket` | `{"acct_id":"A0087","rule_version":"v1"}` | 获取并保存相同标记的样例工单 |
| `rejudge` | `{"old":"v1","new":"v2"}` | 10 个样例账户，3 个状态变化 |

交易时间筛选为闭区间，格式为 `YYYY-MM-DD HH:MM`，例如：

```json
{"acct_id":"A0087","start":"2026-03-03 10:09","end":"2026-03-03 10:52","limit":50}
```

以上范围应返回 `T00415`、`T00431`。建议给智能体添加约束：

> 工具返回 `_demo` 时，必须说明这是固定仿真样例，仅用于演示和联调；不得声称已分析其他账户或全部真实交易。工具报错时如实说明，不得编造证据。

## 六、环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `MCP_MODE` | `fixture` | `fixture` 固定样例；`hybrid` 两个查询 API + 其余 fixture；`real` 要求全部后端 API |
| `MCP_HOST` | `0.0.0.0` | 云端供容器访问；本机独立测试可设 `127.0.0.1` |
| `MCP_PORT` | `8900` | 监听端口 |
| `MCP_TRANSPORT` | `sse` | 对应 `/sse`；`streamable-http` 对应 `/mcp` |
| `MCP_FIXTURES_DIR` | 项目根目录下的 `core/fixtures` | 可指定兼容 JSON 样例目录；建议使用绝对路径 |
| `MCP_DEMO_TICKETS_DIR` | `mcp_server/demo_tickets` | 样例工单目录，与真实 `tickets/` 分开 |
| `USE_STUB` | `1` | 旧配置兼容；未显式设 MCP_MODE 时，1 选样例，其他值选真实模式 |

## 七、常见问题

| 现象 | 检查与处理 |
|---|---|
| 找不到 `core/fixtures/*.json` | 上传完整 fixtures，保留目录结构；不要只上传 server.py |
| Python 版本过低 | 选择服务器已有的 Python 3.10+，再创建虚拟环境 |
| 创建 venv 失败 | 查看原始报错，按服务器发行版补齐对应 Python 的 venv 支持 |
| 安装依赖失败 | 检查服务器网络、pip 索引及错误信息；不要直接跳过安装 |
| `Address already in use` | 执行 `ss -lntp | grep ':8900'` 核实端口占用；确认进程身份后再处理 |
| 宿主机自检通过，Nexent 校验失败 | 检查 Nexent 容器到服务的地址、路由和防火墙；确认监听 `0.0.0.0` |
| URL 可打开但业务调用失败 | 用 selftest.py 做协议自检；普通浏览器打开 SSE 不是完整工具测试 |
| 查询其他账户或 v2 报错 | 当前固定样例不支持；不能靠改字段伪造其他账户或版本的结果 |
| hybrid 启动失败 | 确认部署包包含 core/api.py、core/store.py 和 data/ 三个文件 |
| 切换 real 后部分工具报错 | 当前 core.api 仅实现账户、交易查询；其余工具需由甲完成 API 后才能使用 real |

本地协议与契约测试已完成，但云服务器部署、容器连通性及 Nexent 绑定仍需在实际服务器验收。
英文补充说明见 [DEPLOY.md](DEPLOY.md)。

## 当前文件

| 文件 | 内容 | 产生时间 |
|---|---|---|
| `server.py` | 已注册 hello 和 7 个业务工具；支持 fixture、hybrid、real 三种模式 | 已实现 |
| `selftest.py` | 验证 8 个工具、筛选和错误参数，18 次 MCP 调用 | 已实现 |
| `test_contract.py` | JSON Schema、样例完整性、工单隔离、真实接口委托测试 | 已实现 |
| `DEPLOY.md` | 完整云端部署、上传目录、Nexent 配置和样例限制 | 已提供 |

## 工具清单

`get_account`、`get_transactions`、`trace_chain`、`check_rules`、`make_ticket`、`get_ticket`、`rejudge`，另有测试用的 `hello`。接口以 `Data and Rules/03_判定与输出规范.md` 和 `schemas/*.schema.json` 为准。

## 运行方式

```bash
# 默认样例模式：用现有 core/fixtures/*.json，返回值带 _demo 标记
MCP_MODE=hybrid python mcp_server/server.py

# 仅当所有工具后端均已实现并验收后才使用 real
MCP_MODE=real python mcp_server/server.py

# ECS 后台常驻
nohup env MCP_MODE=hybrid python mcp_server/server.py > mcp.log 2>&1 < /dev/null &
```

## 注意

- 云端部署 hybrid 时必须上传 mcp_server、core、core/fixtures 和 data；详见 DEPLOY.md。
- fixture 模式账户工具仅 A0087；hybrid 模式账户/交易查询读取全量合成数据，但规则输出仍仅 v1、追链仅 max_hops=4、重判仅 v1 到 v2（10 个样例账户）。不是对真实银行数据的分析。
- get_transactions 支持真实的闭区间筛选和 limit 1..200；不支持的样例参数明确报错。
- 样例工单只保存到 mcp_server/demo_tickets，不污染真实 tickets 目录。
- 服务监听端口 8900，**不要暴露到公网**，只放行 Docker 网段。
- 工具出错时不抛异常，返回 `{error, code, detail}`，错误码见 03 规范第 1 节。
- 不得引用 `eval/`。
- 端口和传输方式（`sse` 或 `streamable-http`）以实测为准，结果记入 `agent/README.md`。
