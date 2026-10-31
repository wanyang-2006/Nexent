# tickets/v1/

2026-10-31：按 CHANGELOG 1.0.4 重新生成演示工单，第三方交易描述明确付款方。

规则 v1（`Data and Rules/rules/rules_v1.yaml`）生成的工单，由 `make_ticket(acct_id, "v1")` 写入。

- 文件名：`<账户号>.json`，如 `A0087.json`。
- 工单编号：`TK-v1-<账户号>`。
- 由程序生成，不手工编辑；数据重新生成后需整体删除重做。
- 校验：`python "Data and Rules/validate_spec.py" --skip-spec --data data --tickets tickets/v1`

总说明见上级 `tickets/README.md`。
