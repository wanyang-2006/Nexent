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
