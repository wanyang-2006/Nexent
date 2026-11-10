# Fundtrace A2A 北向接口

部署日期：2026-11-10。服务运行于 ECS `60.205.124.241:8901`，由 systemd 管理（`fundtrace-a2a.service`）。

## 架构

```
外部调用方 (A2A 客户端)
   │  POST http://60.205.124.241:8901/  (A2A protocol)
   ▼
fundtrace-a2a.service  (Starlette + uvicorn, port 8901)
   │  MCP SDK (mcp.client.sse)
   ▼
fundtrace-mcp.service  (FastMCP, port 8900)
   │
   ▼
core.api + data/  (全算法，合成数据集，300账户/2973笔)
```

## 端点

| 方法 | URL | 说明 |
|------|-----|------|
| `GET` | `/.well-known/agent.json` | Agent Card（技能、能力声明） |
| `GET` | `/health` | 健康检查 |
| `POST` | `/` | 任务提交（JSON-RPC 2.0 或简写） |

## 调用格式

### 简写（快速测试）
```json
POST /
{"text": "请按v1研判账户A0209"}
```

### 标准 A2A JSON-RPC
```json
POST /
{
  "jsonrpc": "2.0",
  "id": "req-1",
  "method": "tasks/send",
  "params": {
    "id": "task-001",
    "message": {
      "role": "user",
      "parts": [{"type": "text", "text": "请按v1研判账户A0209"}]
    }
  }
}
```

### SSE 流式（tasks/sendSubscribe）
将 `method` 改为 `"tasks/sendSubscribe"`，响应为 `text/event-stream`，每行一个 `data:` 事件。

## 技能

| skill_id | 触发关键词 | 工具调用链 |
|----------|-----------|-----------|
| `fund-chain-investigation` | `A0xxx`（账户号）+ 可选`v1`/`v2` | `get_account → trace_chain → check_rules → make_ticket` |
| `rule-rejudge` | "重判"、"规则升级"、"变化账户" | `rejudge` |

## 返回结构

```json
{
  "id": "task-001",
  "status": {
    "state": "completed",
    "message": {
      "role": "agent",
      "parts": [
        {"type": "text", "text": "研判完成：A0209 规则版本=v1 结论=..."},
        {"type": "data", "data": {
          "status": "completed",
          "acct_id": "A0209",
          "rule_version": "v1",
          "account": {...},
          "chain": {...},
          "rules": {...},
          "ticket": {...},
          "steps": [...]
        }}
      ]
    }
  },
  "final": true
}
```

## 服务管理

```bash
# 查看状态
sudo systemctl status fundtrace-a2a

# 重启
sudo systemctl restart fundtrace-a2a

# 查看日志
journalctl -u fundtrace-a2a -n 50 --no-pager

# 查看 Agent Card
curl http://127.0.0.1:8901/.well-known/agent.json

# 本地测试
curl -X POST http://127.0.0.1:8901/ \
  -H 'Content-Type: application/json' \
  -d '{"text":"请按v1研判账户A0209"}'
```

## 外网访问

当前阿里云安全组尚未放行 8901 端口（仅内网可用）。
若需外网访问，在阿里云控制台 → 安全组 → 入方向，添加规则：
- 协议：TCP
- 端口范围：8901/8901
- 授权对象：0.0.0.0/0（或限定 IP 段）

## 文件位置

| 文件 | 说明 |
|------|------|
| `/home/Liu/fundtrace-mcp/a2a_server/a2a_server.py` | A2A 服务器主文件 |
| `/etc/systemd/system/fundtrace-a2a.service` | systemd 单元 |
| `D:/NexentFile/.mcp.json` | Claude Code MCP 配置（本机） |
| `D:/NexentFile/.tools/a2a_server.py` | 本地备份 |
