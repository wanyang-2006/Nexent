# core/

甲负责的数据与算法代码。工具接口（`api.py`、`trace.py`、`rules.py`、`ticket.py`、`rejudge.py`）在第 3 天以后加入。

## 文件

| 文件 | 作用 | 可否读 `eval/` | 状态 |
|---|---|---|---|
| `__init__.py` | 空文件，使 `python -m core.xxx` 可用 | — | 第 1 天 |
| `fixtures/*.json` | 7 个工具的假返回值，供乙在真实接口完成前接入（复制自 `Data and Rules/examples/fixtures`，只与样例数据自洽） | — | 第 1 天 |
| `gen_data.py` | 按 `Data and Rules/gen_profile_v1.yaml` 生成 `data/` 与 `eval/` | 可以（写答案） | 第 2 天完成 |
| `verify_injected_chains.py` | 埋入链路核对脚本：逐条检查 12 条链与 D3 是否符合 profile | 可以（只读） | 第 2 天新增 |
| `store.py` | 数据仓库：读 `data/` 两个 CSV，按账户建交易索引；只用标准库 | **不可** | 第 3 天（提前完成） |
| `api.py` | `get_account`、`get_transactions`（已实现）；其余四个函数后续加入 | **不可** | 第 3 天（提前完成） |

规则引擎和工具代码**不得** import `gen_data.py` 或 `verify_injected_chains.py`，也不得引用 `eval/`。

## gen_data.py

```powershell
python -m core.gen_data --force                                   # 正式数据：data/ + eval/（默认 --stage full）
python -m core.gen_data --out _tmp_x --eval-out _tmp_x_eval       # 输出到临时目录（自测、比对哈希）
python -m core.gen_data --stage background --out _tmp_bg          # 只要背景数据（第 1 天口径）
```

已有 `dataset_meta.json` 时不加 `--force` 会拒绝覆盖（退出码 2）；遇到未实现的 profile 选项退出码 3。

流程（全部随机量来自同一个 `random.Random(seed)`）：

```
gen_accounts → pick_pool → plan_chains → gen_background → write_plan × 13 → finalize → 写 CSV / meta / 答案
```

| 函数 | 作用 |
|---|---|
| `gen_accounts` / `pick_pool` | 300 个账户（类型打乱分配）；80 人候选池；2 名 `EMP_MULES` |
| `plan_chains` | **蓝图模式**：一次抽好 12 条链和 D3 的全部细节，然后改新开户日期、登记 `Reservations`。依次调用下面的函数 |
| `plan_ffio` / `plan_layered` / `plan_split` | 快进快出 C01–C06、分层中转 C07–C09、拆分转出 C10–C12 的蓝图（账户、每笔时间与金额、答案行） |
| `plan_withdrawals` | 从全部末端抽 round(0.33 × 末端数) 个，在到账后 10–120 分钟提现到 `CASH`，金额为到账的 50%–100%，同一自然日 |
| `plan_new_accounts` | 一级收款端、中转端、拆分端（`EMP_MULES` 除外）中抽一半，开户日期改为 03-01 前 10–25 天 |
| `plan_d3` | D3 合租转发：池外个人 F、P、L，第二家企业给 P 发 1 笔工资 |
| `check_plan` | 蓝图自检：同一自然日、不越界、C03 的转账在 04:00 前结束 |
| `reserve_plan` | 登记静默期与首次对手约束（见下） |
| `gen_personal_transfers` / `gen_consumption` / `gen_salary` | 背景交易。个人互转避开 `Reservations`；工资企业不选 D3 的第二家企业，员工不含候选池（`EMP_MULES` 除外）和 D3 三方 |
| `write_plan` | 只照蓝图写交易与答案行，不再抽随机数；链上 `转账` 记入 `answer_tx` |
| `background_answer_rows` / `order_answer` | D1、D2 答案行；答案排序（涉诈行在前，干扰按 工资、商户、合租转发） |
| `finalize` / `write_csv` / `write_meta` | 按 (time, 生成顺序) 编号 `T00001…`；UTF-8 无 BOM、LF；meta 含 sha256、不含生成时间 |

### 关键取舍

- **蓝图在背景之前**：先确定链上账户和时间，背景交易才能主动避开。不要在背景生成后去找“恰好干净”的账户（每人每天约 1.6 笔互转，11 个账户的拆分链几乎找不到）。
- **静默期按整个自然日**（`chain_common.quiet_scope: natural_day`）：范围 = [首笔 − 180, 末笔 + 180] ∪ 链路所在自然日，末笔含提现。原因是 R04 按自然日统计出入比（≥ 0.95），当天混入约 1000 元背景转入就会失效。只约束 `转账`；消费、工资不受影响（规则不把它们算作转账）。
- **首次对手**：同一条链上任意两个账户之间，除蓝图里的交易外没有任何交易（包括背景互转）。
- **R02 防护**（`chain_common.r02_guard`）：v1 应为“未见异常”的账户（C05、C06 的受骗方，D3 的 F、P、L），背景转入不得在 60 分钟内凑满 3 个来源，否则这些账户的预期状态会随 seed 漂移。参数取自 `rules_v1.yaml` 的 R02。
- **日期**：12 条链按 rng 打乱后轮流分到 7 天（第 1–5 天各 2 条，第 6、7 天各 1 条）。D3 固定在 03-04。
- **账户**：除 `EMP_MULES` 外，链上账户从候选池（78 人）按抽取顺序不放回分配；seed 42 用掉 67 人。
- background 阶段的输出与第 1 天逐字节相同（`plan_chains` 不运行时 D3 的排除集合为空）。

### 实测（seed 42）

- 交易 2973 笔：转账 1459（背景 1400 + 链上 57 + D3 2）、消费 1472、工资 31、提现 11。
- 12 条链 57 笔链上转账；新开户 8 个（合格槽位 16 个）；答案 132 行（涉诈 69、干扰 63）。
- 同 seed 两次生成，`data/` 三个文件和 `eval/` 两个文件的 sha256 均相同。
- seed 1–20 与 42 共 21 个 seed：`verify_injected_chains.py` 全部 0 错误，交易数 2954–3035。

## verify_injected_chains.py

```powershell
python core/verify_injected_chains.py                                # 核对 data/ 与 eval/
python core/verify_injected_chains.py --data _tmp_x --answers _tmp_x_eval
```

按路径加载 `Data and Rules/validate_spec.py`，调用其中的追链参考实现 `reference_chains`。检查项：

1. **答案结构**：链集合等于 profile；答案账户与 `answer_tx` 的交易一一对应；链与链不共用账户；`EMP_MULES` 在 C04 一级收款端和 C08 的 L2。
2. **追链**：分别按 v1、v2 追链，检出集合等于 `expectations.chain_detected`（v1 10 条、v2 12 条）；检出的链与答案的交易集合、角色、hops（快进快出、拆分为 2，分层为 4）完全一致；除 v2 下的 D3 外不得有其他链。
3. **时间与金额**：首笔时间、受骗金额与人数、入账间隔、停留时间、转出比例、分层首跳延迟与每跳间隔、每跳衰减、拆分笔数、单笔金额、收款方互不相同、拆分延迟与跨度、合计比例。
4. **提现**：笔数、比例、延迟、同一自然日，且只出现在末端。
5. **新开户**：只出现在合格槽位，个数为一半，开户距起始日 10–25 天。
6. **静默期与首次对手**：12 条链和 D3 共 13 组。
7. **D3**：两笔转账的时间与金额、P 的工资来自第二家企业（只发 1 笔，答案登记为 `工资`）、三方不是工资员工、P 当日出入比在 [R01 0.9, R04 0.95) 之间。
8. **R02**：防护账户未命中；C03 的一级收款端命中（设计要求）。

最后打印每条链的汇总表。退出码 0 表示全部通过。

## store.py 与 api.py（数据查询层）

```text
Nexent 智能体 → mcp_server/server.py（乙：接线） → core/api.py（甲：函数） → core/store.py（档案柜） → data/*.csv
```

- `store.py` 启动时一次性读入 `accounts.csv`、`transactions.csv`，建好 `by_acct`（账户 → 其全部交易，按 `(time, tx_id)` 升序）。以后的 `trace.py`、`rules.py`、`ticket.py` 共用这份数据。数据目录默认 `data/`，可用环境变量 `FUNDTRACE_DATA_DIR` 改（部署时挂载只读卷用）。数据改动后需重启服务。
- `api.py` 的函数一律返回 dict、不抛异常，未预期异常转成 `INTERNAL` 错误。

| 函数 | 说明 |
|---|---|
| `get_account(acct_id)` | 统计全部交易类型；提现计入转出；`counterparty_count` 去重且不含 `CASH`；无交易时 `first_tx_time`、`last_tx_time` 为 `null` |
| `get_transactions(acct_id, start=None, end=None, limit=50)` | `start`/`end` 闭区间，格式 `YYYY-MM-DD HH:MM`，空串视为不限；`limit` 1 至 200（`None` 取 50）；`total` 是范围内总数，`truncated = total > count` |

输入处理：账户号先去首尾空白并转大写，再校验 `^A\d{4,}$`，格式不对返回 `BAD_PARAM`，格式对但不存在返回 `ACCOUNT_NOT_FOUND`；时间格式或日期不合法返回 `BAD_TIME_FORMAT`；`start` 晚于 `end`、`limit` 越界或不是整数返回 `BAD_PARAM`。

### 给乙的接入说明

1. `git pull`，确认有 `core/store.py`、`core/api.py`。`server.py` 里按模式切换，**逐个工具切换**，不要等四个函数全部完成：

```python
import os
MODE = os.environ.get("MCP_MODE", "fixture")      # fixture | real

if MODE == "real":
    from core import api
    # get_account / get_transactions 调 api；其余四个工具暂时仍读 fixtures
```

2. 注意事项：
   - 函数返回的就是 03 规范规定的 JSON 对象，**不要再包一层**；`get_transactions` 的键名是 `transactions`。
   - 云端必须能 `import core`：服务从仓库根目录启动，或把根目录加入 `PYTHONPATH`。
   - 云端需要仓库里的 `data/` 目录。**不需要** `eval/`，也不要复制过去（答案表不应出现在服务器上的服务目录里）。
   - 只用标准库，不要求云端安装 pandas。
3. 验证（在云端仓库根目录）：

```bash
python -c "from core import api; import json; print(json.dumps(api.get_account('A0209'), ensure_ascii=False, indent=1))"
python -c "from core import api; print(api.get_transactions('A0283', limit=5)['total'])"
python -m pytest tests -q          # 需要 pip install pytest jsonschema referencing
```

   期望（已按 `data/transactions.csv` 手工核算）：`get_account('A0209')` 为 `in_count 6、in_amount 75241、out_count 9、out_amount 72356、counterparty_count 14、first_tx_time 2026-03-01 09:14、last_tx_time 2026-03-07 21:54`；样例 A0087 的 `in_amount` 是 68000，不应出现；`A9999` 返回 `ACCOUNT_NOT_FOUND`。
4. 切换后，提示词、Skill、测试中的账户号换成 `eval/demo_accounts.md` 里的“替换表”。
5. 重启 MCP 服务并在 Nexent 点“刷新工具”。

## 测试

```powershell
python -m pytest tests -q
```

`tests/test_api_queries.py` 包含：样例数据下与 `fixtures` 逐字段相等；正式数据下 300 个账户全部与“逐行暴力统计”一致并通过 schema 校验；已知交易锚点；时间范围、`limit`、各类错误输入；输出可复现；返回值是副本；代码不引用 `eval/`。依赖 `pytest`、`jsonschema`、`referencing`。

## 变更记录

- 第 3 天（提前）：新增 `store.py`、`api.py`（`get_account`、`get_transactions`）与 `tests/test_api_queries.py`。
- 第 1 天：`gen_data.py` 背景部分、`fixtures/`、`__init__.py`。
- 第 2 天：
  - `gen_data.py` 实现埋链。原计划的 `inject_ffio / inject_layered / inject_split / inject_d3` 改为蓝图模式：`plan_ffio / plan_layered / plan_split / plan_d3` 加统一的 `write_plan`；新增 `plan_withdrawals`、`plan_new_accounts`、`check_plan`、`reserve_plan`、`order_answer`。
  - `Reservations` 新增 `src_guard`（R02 防护）和 `note_transfer`；首次对手扩大为链上任意两个账户。
  - `gen_salary` 排除 D3 的第二家企业与 F、P、L。
  - `--stage` 默认值由 `background` 改为 `full`。
  - 新增 `verify_injected_chains.py`。
