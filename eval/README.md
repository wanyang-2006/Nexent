# eval/

评测与答案目录，由甲维护。这里的内容只用于评测和演示准备，**工具运行时不得读取**。

## 约束

- `core/api.py` 及所有 MCP 工具禁止引用本目录，否则等于把答案交给了系统。
- 答案信息（链编号、角色、模式）只出现在本目录，不得写入 `data/`。
- `python "Data and Rules/validate_spec.py" --skip-spec --data data --check-leak core` 会扫描代码有没有读取这里的文件。

## 计划放入的文件

| 文件 | 内容 | 产生时间 |
|---|---|---|
| `answer.csv` | 涉案账户答案：`acct_id, chain_id, pattern, role`；干扰账户 `chain_id` 留空、`role=无` | 第 2 天，`gen_data.py --stage full` |
| `answer_tx.csv` | 每条链的账户间转账交易号（可选，不含提现） | 第 2 天 |
| `demo_accounts.md` | 演示问题 Q1 至 Q5 各用哪个账户，以及 v1、v2 的预期状态 | 第 2 天，交乙 |
| `selfcheck_v1.txt`、`selfcheck_v2.txt` | 每个涉案账户命中的规则、状态、是否被追到 | 第 3 至 4 天 |
| `assets_manifest.csv` | 资产登记表：`asset_id, asset_type, title, source, version, sha256, is_synthetic` | 第 5 天以后 |
| `graphs/<chain_id>.png` | 资金链图 | 第 5 天以后（可选） |

## 注意

- 第 2 天数据冻结后，`answer.csv` 与 `data/` 一一对应，不要单独重新生成其中一个。
- 所有评测结果都要注明 `data/dataset_meta.json` 里的 `dataset_id`。
