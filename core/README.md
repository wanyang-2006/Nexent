# core/

甲负责的数据与算法代码。六个工具函数统一从 `api.py` 导出，算法分别在 `trace.py`、`rules.py`、`ticket.py`、`rejudge.py` 中实现。

## 文件

| 文件 | 作用 | 可否读 `eval/` | 状态 |
|---|---|---|---|
| `__init__.py` | 空文件，使 `python -m core.xxx` 可用 | — | 第 1 天 |
| `fixtures/*.json` | 7 个工具的假返回值，供乙在真实接口完成前接入（复制自 `Data and Rules/examples/fixtures`，只与样例数据自洽） | — | 第 1 天 |
| `gen_data.py` | 按 `Data and Rules/gen_profile_v1.yaml` 生成 `data/` 与 `eval/` | 可以（写答案） | 第 2 天完成 |
| `verify_injected_chains.py` | 埋入链路核对脚本：逐条检查 12 条链与 D3 是否符合 profile | 可以（只读） | 第 2 天新增 |
| `store.py` | 数据仓库：读 `data/` 两个 CSV，按账户建交易索引；带派生结果缓存 `cached()`；只用标准库 | **不可** | 第 3 天（提前完成） |
| `api.py` | 六个工具函数的参数校验与导出（乙的 `server.py` 只调用这里） | **不可** | 六个函数已全部实现 |
| `ruleset.py` | 读规则 YAML 与 `enums.yaml`、追链窗口、规则差异 `rules_diff`、时间换算等公用工具 | **不可** | 新增 |
| `trace.py` | 资金链追踪：移植 `validate_spec.py` 的 `reference_chains`，按规则版本全量计算并缓存；`max_hops` 裁剪 | **不可** | 新增 |
| `rules.py` | 规则引擎：R01–R11 共 11 个 impl，按 YAML 的 `impl` 分发（`IMPLS`） | **不可** | 新增 |
| `ticket.py` | 角色与状态判定 `judge`、工单组装 `ticket_result`、落盘 `write_ticket` | **不可** | 新增 |
| `rejudge.py` | 全部账户按两个规则版本重判，列出状态变化与原因 | **不可** | 新增 |
| `export_rules_md.py` | 把规则 YAML 渲染成 `kb/rules_v1.md`、`rules_v2.md`、`rules_diff_v1_v2.md` | 不需要 | 新增 |
| `selfcheck.py` | 自检：答案表每个账户的命中规则、角色、状态、是否追到，演示账户与设计预期对照；写 `eval/selfcheck_v*.txt` | 可以（白名单） | 新增 |
| `evaluate.py` | 评测：识别链路数、账户召回、误报、背景告警、v1→v2 状态变化；写 `eval/result.md` | 可以（白名单） | 新增 |
| `baseline_compare.py` | 对照基线：B1 单笔 ≥ 10000 元转账即告警；B2 不看时间窗与守恒的追链。只给出判定与链，打分在 `evaluate.py` | 不读 | 新增（10-30） |
| `export_graph.py` | 把追链结果画成 PNG，写 `eval/graphs/<版本>_<链号>.png`（只用 matplotlib，不依赖 networkx） | 只写不读答案 | 新增（10-30），已登记白名单（1.0.3） |
| `export_assets_manifest.py` | 资产登记表，写 `eval/assets_manifest.csv`（不写生成时间，重复运行结果不变） | 只写不读答案 | 新增（10-30），已登记白名单（1.0.3） |
| `run_checks_jia.py` | 甲的一键核验：把“核验”一节的步骤串起来（现为 12 步，10-30 增加链路图与资产登记），最后汇总通过/失败 | 不读（由白名单脚本自己读） | 新增 |

规则引擎和工具代码（`api`、`ruleset`、`trace`、`rules`、`ticket`、`rejudge`、`store`）**不得** import `gen_data.py`、`verify_injected_chains.py`、`selfcheck.py`、`evaluate.py`，也不得引用 `eval/`（`tests/test_engine.py` 会检查）。

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

1. `git pull`，确认有 `core/store.py`、`core/api.py` 以及 `ruleset.py`、`trace.py`、`rules.py`、`ticket.py`、`rejudge.py`。六个函数都已实现，`server.py` 仍建议**逐个工具切换**（先切 `get_account`、`get_transactions`，联调通过再切其余四个），出问题时可单个退回 fixture：

```python
import os
MODE = os.environ.get("MCP_MODE", "fixture")      # fixture | real

if MODE == "real":
    from core import api
    # api.get_account / get_transactions / trace_chain / check_rules / make_ticket / rejudge
```

2. 注意事项：
   - 函数返回的就是 03 规范规定的 JSON 对象，**不要再包一层**；`get_transactions` 的键名是 `transactions`。
   - 云端必须能 `import core`：服务从仓库根目录启动，或把根目录加入 `PYTHONPATH`。
   - 云端需要仓库里的 `data/` 目录。**不需要** `eval/`，也不要复制过去（答案表不应出现在服务器上的服务目录里）。
   - 只用标准库，不要求云端安装 pandas。
   - 规则引擎需要 `pyyaml`，并读取仓库里的 `Data and Rules/rules/` 与 `enums.yaml`，云端要一并部署（不含 `eval/`）。
   - `make_ticket` 会写 `tickets/<版本>/<账户>.json`，服务进程对 `tickets/` 要有写权限；可用环境变量 `FUNDTRACE_TICKET_DIR` 改目录。
   - 规则版本参数接受 `v1`、`V1 ` 等写法（去空白转小写）；不存在的版本返回 `BAD_RULE_VERSION`。
3. 验证（在云端仓库根目录）：

```bash
python -c "from core import api; import json; print(json.dumps(api.get_account('A0209'), ensure_ascii=False, indent=1))"
python -c "from core import api; print(api.get_transactions('A0283', limit=5)['total'])"
python -m pytest tests -q          # 需要 pip install pytest jsonschema referencing
```

   期望（已按 `data/transactions.csv` 手工核算）：`get_account('A0209')` 为 `in_count 6、in_amount 75241、out_count 9、out_amount 72356、counterparty_count 14、first_tx_time 2026-03-01 09:14、last_tx_time 2026-03-07 21:54`；样例 A0087 的 `in_amount` 是 68000，不应出现；`A9999` 返回 `ACCOUNT_NOT_FOUND`。
4. 切换后，提示词、Skill、测试中的账户号换成 `eval/demo_accounts.md` 里的“替换表”。
5. 重启 MCP 服务并在 Nexent 点“刷新工具”。

## 追链、规则、工单、重判（实现要点）

| 函数 | 实现 | 要点 |
|---|---|---|
| `trace_chain(acct_id, max_hops=4, rule_version="v1")` | `trace.py` | 链接图 + 弱连通分量，逐行移植 `reference_chains`；每个版本全量算一次并缓存在 `store.cached(("trace", 版本))`。`max_hops` 只裁剪 `edges`：保留两端距起点都 ≤ `max_hops` 的边，不足 2 条（schema 要求）时放宽为至少一端 ≤ `max_hops` |
| `check_rules(acct_id, rule_version="v1")` | `rules.py` | `IMPLS` 按 `impl` 分发；YAML 中出现未实现的 impl 返回 `INTERNAL`。聚合窗口从锚点交易起（同一分钟按 `tx_id`），前向窗口按分钟取 `(t, t+W]`；多个窗口命中取规则表写明的代表窗口，并列取最早；`detail` 带日期时间与关键数字 |
| `make_ticket(acct_id, rule_version="v1")` | `ticket.py` | 状态按 03 规范第 4 节顺序判定；支持证据 = 本账户在主链上的边优先，再用风险规则证据补足，最多 10 条、按时间升序；“证据不足”且在链上时，结论前加“该账户在资金链 … 中表现为…，”以满足“在链上须含 chain_id” |
| `rejudge(old="v1", new="v2")` | `rejudge.py` | 300 个账户各判两次；`reason` 按模板拼接；同一条链上仅角色变化时写“在资金链 … 中的角色由…变为…” |

## 核验（简化版：一条命令）

```powershell
python core/run_checks_jia.py           # 全部 10 步
python core/run_checks_jia.py --fast    # 跳过 pytest 与埋链核对
```

| 步骤 | 内容 | 失败时先看 |
|---|---|---|
| 1 环境 | Python ≥ 3.11；pyyaml、jsonschema、referencing、pytest | `pip install -r requirements.txt` |
| 2 规范自检 | `validate_spec.py`（枚举、规则、生成配置、样例） | 规范文件是否被改动 |
| 3 fixtures | `core/fixtures` 与样例数据一致 | 乙是否改过 fixtures |
| 4 数据与防泄题 | `data/` 格式与 sha256；`core`、`mcp_server` 不引用答案目录 | sha256 不符说明冻结数据被改了 |
| 5 埋链核对 | `verify_injected_chains.py` | — |
| 6 单元测试 | `pytest tests -q` | 失败的测试名 |
| 7 规则文档 | 重新生成 `kb/rules_*.md` | — |
| 8 自检 | `eval/selfcheck_v1.txt`、`v2.txt`；终端打印角色与演示账户不一致的账户 | selfcheck 文件里“否”的行 |
| 9 评测 | `eval/result.md` | — |
| 10 工单 | 10 个演示账户的 v1、v2 工单写入 `tickets/`，再用 `validate_spec.py --tickets` 校验 | — |

失败的步骤会打印最后 40 行输出；完整日志在 `_tmp_checks/run_checks_jia_log.txt`。

## 测试

```powershell
python -m pytest tests -q
```

`tests/test_api_queries.py` 包含：样例数据下与 `fixtures` 逐字段相等；正式数据下 300 个账户全部与“逐行暴力统计”一致并通过 schema 校验；已知交易锚点；时间范围、`limit`、各类错误输入；输出可复现；返回值是副本；代码不引用 `eval/`。依赖 `pytest`、`jsonschema`、`referencing`。

`tests/test_engine.py` 包含：样例数据下 `trace_chain`、`rejudge` 与 fixtures 完全相等，`check_rules`、`make_ticket` 除 `detail`/`conclusion` 措辞外相等；正式数据下 v1、v2 的全部链与参考实现 `reference_chains` 逐条一致（设计值 v1 10 条、v2 13 条＝12 条埋入链 + D3）；300 个账户 × 两个版本全部通过 schema 和工单语义检查；`max_hops` 只裁剪边；`rejudge` 汇总自洽；03 规范典型结果的几个设计预期；错误参数；工具模块不 import 答案脚本。

## 变更记录

- 2026-10-29（第 3 至 5 天内容提前）：新增 `ruleset.py`、`trace.py`、`rules.py`、`ticket.py`、`rejudge.py`、`export_rules_md.py`、`selfcheck.py`、`evaluate.py`、`run_checks_jia.py`；`api.py` 导出其余四个函数；`store.py` 增加 `cached()` 与 `start_date`；新增 `tests/test_engine.py`。**编写时所在环境无法运行 Python，以上代码只做过静态核对，以本机运行 `python core/run_checks_jia.py` 的结果为准。**
- 第 3 天（提前）：新增 `store.py`、`api.py`（`get_account`、`get_transactions`）与 `tests/test_api_queries.py`。
- 第 1 天：`gen_data.py` 背景部分、`fixtures/`、`__init__.py`。
- 第 2 天：
  - `gen_data.py` 实现埋链。原计划的 `inject_ffio / inject_layered / inject_split / inject_d3` 改为蓝图模式：`plan_ffio / plan_layered / plan_split / plan_d3` 加统一的 `write_plan`；新增 `plan_withdrawals`、`plan_new_accounts`、`check_plan`、`reserve_plan`、`order_answer`。
  - `Reservations` 新增 `src_guard`（R02 防护）和 `note_transfer`；首次对手扩大为链上任意两个账户。
  - `gen_salary` 排除 D3 的第二家企业与 F、P、L。
  - `--stage` 默认值由 `background` 改为 `full`。
  - 新增 `verify_injected_chains.py`。
- 2026-10-30：新增 `baseline_compare.py`（B1、B2 基线）、`export_graph.py`（链路图）、`export_assets_manifest.py`（资产登记表）；`evaluate.py` 增加基线打分，运行时同时写 `eval/baseline.md`（`result.md` 内容未变，已核对）；`run_checks_jia.py` 增加第 11、12 步。已登记防泄题白名单（`Data and Rules/CHANGELOG.md` 1.0.3）：`export_graph.py`、`export_assets_manifest.py` 的输出路径含 `eval/`，但只写不读答案。
