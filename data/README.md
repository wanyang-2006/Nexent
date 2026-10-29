# data/

仿真交易数据，由 `core/gen_data.py` 生成，工具（`core/api.py`、`mcp_server/`）只读本目录。格式见 `Data and Rules/01_数据规范.md` 与 `data_schema_v1.yaml`。

**数据已冻结**（第 2 天）。不要重新生成覆盖；确需重新生成（`python -m core.gen_data --force`）时，必须同时更新 `eval/demo_accounts.md` 并通知乙，因为账户号、交易号都会变。

## 文件

| 文件 | 内容 |
|---|---|
| `accounts.csv` | `acct_id, name, acct_type, open_date`，300 行 |
| `transactions.csv` | `tx_id, time, from_acct, to_acct, amount, tx_type`，按 (time, tx_id) 升序，2973 行 |
| `dataset_meta.json` | dataset_id、seed、时间范围、行数、两个 CSV 的 sha256；不含生成时间和任何答案信息 |

本目录**不含任何标签**；哪些账户涉诈只记录在 `eval/`。

## 数据生成说明（seed 42，可转交丙）

1. 数据集 `sim-gen_profile_v1-seed42`，全部为合成数据（`source: synthetic`），随机种子 42，同 seed 可逐字节复现；时间范围 2026-03-01 00:00 至 2026-03-07 23:59。
2. 账户 300 个：个人 250、商户 30、企业 20，编号打乱分配，名称为合成名（如 `用户0001`）。
3. 交易 2973 笔：个人小额互转 1400 笔（50–2000 元）、消费 1472 笔（5 家高频商户 + 25 家普通商户）、工资 31 笔、链上转账 57 笔、D3 转账 2 笔、提现 11 笔。
4. 埋入 3 种涉诈资金模式共 12 条链：快进快出 6 条、分层中转 3 条、拆分转出 3 条，每个受骗方转出 25000–50000 元，分布在 7 天内。
5. 干扰：发工资的企业与员工、30 家商户、合租转发（朋友转房租后 90 分钟转给房东）各一类，用于检验误报。

## 校验

```powershell
python "Data and Rules/validate_spec.py" --skip-spec --data data --eval eval
python core/verify_injected_chains.py
```

## 变更记录

- 第 1 天：开发用背景数据（2937 笔，无诈骗链，已随 `68c744a` 提交；第 2 天的重新生成会在 git 中显示为修改）。
- 第 2 天：用 `--stage full --force` 重新生成正式数据并冻结。sha256：`accounts.csv` bcc91394c0f8…，`transactions.csv` 51a1b0e3f3ca…（完整值见 `dataset_meta.json`）。
