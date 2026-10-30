# eval/

评测与答案目录，由甲维护。这里的内容只用于评测和演示准备，**工具运行时不得读取**。

## 约束

- `core/api.py` 及所有 MCP 工具禁止引用本目录，否则等于把答案交给了系统。
- 答案信息（链编号、角色、模式）只出现在本目录，不得写入 `data/`。
- `python "Data and Rules/validate_spec.py" --skip-spec --data data --eval eval --check-leak core mcp_server` 会扫描代码有没有读取这里的文件。允许引用本目录的只有 `gen_data.py`、`verify_injected_chains.py`、`evaluate.py`、`selfcheck.py`、`import_amlsim.py`。

## 文件

| 文件 | 内容 | 产生方式 | 状态 |
|---|---|---|---|
| `answer.csv` | 账户级答案：`acct_id, chain_id, pattern, role` | `python -m core.gen_data --force` 与 `data/` 一起生成 | 已生成（第 2 天） |
| `answer_tx.csv` | 每条链的账户间 `转账`：`tx_id, chain_id`（不含提现） | 同上 | 已生成（第 2 天） |
| `demo_accounts.md` | 演示问题 Q1、Q2、Q3、Q5 和备用账户，以及 v1、v2 的预期状态 | 手写，交乙 | 已写，状态已改为 2026-10-29 实测，含 8 个变化账户与 T01942 |
| `selfcheck_v1.txt`、`selfcheck_v2.txt` | 每个答案账户的命中规则、角色、状态、是否追到；答案链识别情况；演示账户实测与设计预期对照；背景账户告警 | `python -m core.selfcheck` | 脚本已写，待本机运行生成 |
| `result.md` | 评测结果表（v1、v2 两列）、明细与 v1→v2 状态变化 | `python -m core.evaluate` | 已生成 |
| `baseline.md` | 对照基线：B1 单笔规则、B2 无时序追链与本作品 v1、v2 对比，附由数字生成的解读 | `python -m core.evaluate`（与 `result.md` 同时写出） | 已生成（10-30） |
| `nexent_evalset.md` | 给乙建 Nexent 评测集用：5 条用例的必须出现/不得出现要点，加人工核对参考表（均为实测值） | 手写，依据 selfcheck 与工单 | 已写（第 5 天） |
| `给乙_第5天修改说明.md` | 乙第 5 天的操作清单：评估打分、提示词与 Skill 的可直接粘贴的修改、记录表、晚间决策规则 | 手写 | 已写（第 5 天） |
| `assets_manifest.csv` | 资产登记表：`asset_id, asset_type, title, source, version, sha256, is_synthetic` | `python -m core.export_assets_manifest`（脚本生成，请勿手改） | 已生成（10-30），13 条 |
| `graphs/<版本>_<chain_id>.png` | 资金链图：v1 的 L-T01908、L-T01001，v2 的 L-T01338、L-T01454 | `python -m core.export_graph` | 已生成（10-30） |

## answer.csv 的内容（seed 42）

共 132 行：涉诈 69 行 + 干扰 63 行。

- **涉诈行**（12 条链 C01 至 C12）：按 `chain_id`、角色（疑似受骗付款端 → 一级收款端 → 中转端 → 拆分端 → 末端）、`acct_id` 排序。角色与 03 规范第 3 节的系统判定一致：快进快出的 A、分层的 L1 为一级收款端；L2、L3 为中转端；拆分端；其余为末端。2 名 `EMP_MULES` 只登记在所在链（C04 一级收款端、C08 的 L2）。
- **干扰行**（`chain_id` 为空、`role=无`），依次为：
  - `工资`：工资企业 1 + 纯员工 28 + D3 的第二家企业 1 = 30
  - `商户`：30
  - `合租转发`：D3 的 F、P、L = 3
- 误报分母：干扰账户 63 个。不在本表中的账户为背景账户，评测时单独统计。

## answer_tx.csv 的内容（seed 42）

57 行，只含链上账户之间的 `转账`；11 笔末端提现（到 `CASH`）和 D3 的两笔转账不在其中。按 `tx_id` 升序。

## 核对

```powershell
python core/verify_injected_chains.py          # 逐条核对 12 条链与 D3（读本目录）
python "Data and Rules/validate_spec.py" --skip-spec --data data --eval eval
```

## 注意

- 数据已冻结：`answer.csv`、`answer_tx.csv` 与 `data/` 一一对应，不要单独重新生成其中一个。确需重新生成（`--force`）时同时更新 `demo_accounts.md` 并通知乙。
- 所有评测结果都要注明 `data/dataset_meta.json` 里的 `dataset_id`（当前为 `sim-gen_profile_v1-seed42`）。

## 变更记录

- 2026-10-29：`core/selfcheck.py`、`core/evaluate.py` 已编写，分别生成 `selfcheck_v*.txt` 与 `result.md`（尚未运行，文件生成后以其中数字为准）。一键运行见 `core/README.md` 的“核验”一节。
- 第 2 天：生成 `answer.csv`、`answer_tx.csv`（seed 42）；新增 `demo_accounts.md`；`verify_injected_chains.py` 加入允许读取本目录的名单。
- 2026-10-30：`demo_accounts.md` 改为实测；新增 `baseline.md`、`assets_manifest.csv`、`graphs/`（4 张）。`export_graph.py`、`export_assets_manifest.py` 向本目录写文件但不读答案，已登记进防泄题白名单（CHANGELOG 1.0.3）。
- 2026-11-02（第 5 天）：新增 `nexent_evalset.md`、`给乙_第5天修改说明.md`。评测集中的状态、角色、链号、规则、缺失证据代码均对照 `selfcheck_v1.txt`、`selfcheck_v2.txt`、`tickets/` 与 `core.api` 的实测核对；A0074 的工单字段由 `core.api.make_ticket` 现场复核。
