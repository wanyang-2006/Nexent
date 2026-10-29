# tickets/

证据工单目录，由甲维护（程序生成，不手工编辑）。`make_ticket(acct_id, rule_version)` 每生成一份工单，就按规则版本保存到对应子目录。

## 子目录

| 目录 | 内容 |
|---|---|
| `v1/` | 规则 v1 生成的工单 |
| `v2/` | 规则 v2 生成的工单 |

## 约定

- 文件路径：`tickets/<版本>/<账户号>.json`，如 `tickets/v1/A0087.json`。
- 工单编号：`TK-v<版本号>-<账户号>`，如 `TK-v1-A0087`。
- 工单格式由 `Data and Rules/schemas/make_ticket.schema.json` 约束，字段含义见 `03_判定与输出规范.md` 第 5 节。
- 乙的 `get_ticket` 读取这里的文件；不存在时调用 `make_ticket` 生成。

## 校验

```bash
python "Data and Rules/validate_spec.py" --skip-spec --data data --tickets tickets/v1
```

检查内容：工单 schema、`tx_id` 是否存在、`missing_evidence` 首项、禁用词、`status_code` 与 `rule_basis` 是否与规则文件一致。

## 注意

- 数据重新生成后，旧工单里的交易号会失效，需要删除重新生成。
- 工单只用于辅助研判，不是对账户的定性。
- 运行 `python core/run_checks_jia.py` 会为 10 个演示账户（见 `eval/demo_accounts.md`）生成 v1、v2 工单并校验；测试运行时工单写到临时目录，不进入本目录。
- 部署时可用环境变量 `FUNDTRACE_TICKET_DIR` 把工单目录改到别处。

## 变更记录

- 2026-10-29：`core/ticket.py` 已实现 `make_ticket` 的落盘（UTF-8、LF、indent=2）；尚未在本机运行生成工单。
