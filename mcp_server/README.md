# mcp_server/

MCP 服务目录，由乙维护。把甲的 6 个核心函数加上 `get_ticket` 包装成 MCP 工具，供 Nexent 智能体调用。

## 计划放入的文件

| 文件 | 内容 | 产生时间 |
|---|---|---|
| `server.py` | 基于 FastMCP 的服务，先只有 `hello`，再换成 7 个业务工具（骨架见乙文档附录 A） | 第 1 天 |
| `restart.sh` | 在 ECS 上重启服务的脚本（可选 systemd 单元） | 第 5 天以后 |

## 工具清单

`get_account`、`get_transactions`、`trace_chain`、`check_rules`、`make_ticket`、`get_ticket`、`rejudge`，另有测试用的 `hello`。接口以 `Data and Rules/03_判定与输出规范.md` 和 `schemas/*.schema.json` 为准。

## 运行方式

```bash
# 第 1 天：用 core/fixtures/*.json 作为假数据
USE_STUB=1 python mcp_server/server.py

# 第 3 天起：去掉 USE_STUB，调用 core/api.py 的真实实现
python mcp_server/server.py

# ECS 后台常驻
nohup python mcp_server/server.py > mcp.log 2>&1 &
```

## 注意

- 服务监听端口 8900，**不要暴露到公网**，只放行 Docker 网段。
- 工具出错时不抛异常，返回 `{error, code, detail}`，错误码见 03 规范第 1 节。
- 不得引用 `eval/`。
- 端口和传输方式（`sse` 或 `streamable-http`）以实测为准，结果记入 `agent/README.md`。
