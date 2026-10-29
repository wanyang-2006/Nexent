# tickets/v2/

规则 v2（`Data and Rules/rules/rules_v2.yaml`）生成的工单，由 `make_ticket(acct_id, "v2")` 或 `rejudge` 写入。

- 文件名：`<账户号>.json`，如 `A0087.json`。
- 工单编号：`TK-v2-<账户号>`。
- 与 `v1/` 对照可以看出规则升级后哪些账户的结论变了（C05、C06 及 D3 相关账户是设计好的演示对象）。
- 由程序生成，不手工编辑；数据重新生成后需整体删除重做。
- 校验：`python "Data and Rules/validate_spec.py" --skip-spec --data data --tickets tickets/v2`

总说明见上级 `tickets/README.md`。
