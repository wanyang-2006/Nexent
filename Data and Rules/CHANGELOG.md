# CHANGELOG

格式：每个版本按"新增 / 变更 / 修复"列出，并注明影响方（甲 = 数据与算法，乙 = Nexent 与工具接入，文档 = 开发指南与任务书）。

## 1.0.3 — 2026-10-30（只调整防泄题白名单，函数契约与字段不变）

- `validate_spec.py --check-leak` 的白名单新增 `export_graph.py`、`export_assets_manifest.py`：两者只把链路图、资产登记表写入 `eval/`，不读答案文件。`01_数据规范.md`、`README.md` 同步说明。工具代码（`api`、`trace`、`rules`、`ticket`、`rejudge`、`mcp_server/`）的限制不变。（甲）
- `core/evaluate.py` 在写 `eval/result.md` 的同时写 `eval/baseline.md`（对照基线）；`result.md` 的内容与口径不变。（甲）

## 1.0.2 — 2026-10-29（四个算法函数的实现细则，字段不变）

`core/trace.py`、`rules.py`、`ticket.py`、`rejudge.py` 实现时对 02、03 规范未写明处的取舍，乙的 `server.py` 与提示词按此对接（代码尚未在本机运行，以运行结果为准）：

- 规则版本参数先去首尾空白并转小写（`" V2"` 等同 `"v2"`）；不是 `^v\d+$` 或规则文件不存在都返回 `BAD_RULE_VERSION`。`max_hops` 为 `None` 时取 4，不是 1 至 10 的整数（含布尔）返回 `BAD_PARAM`。校验顺序：账户格式 → 规则版本 → 其他参数 → 账户是否存在。（甲、乙）
- `trace_chain` 的 `max_hops` 只裁剪 `edges`：保留两端距查询账户都 ≤ `max_hops` 的边；不足 2 条时（schema 要求 `edges` 至少 2 条）放宽为至少一端 ≤ `max_hops`。`accounts`、`tx_ids`、`roles` 与统计字段始终描述整条链。（甲、乙）
- `check_rules` 的窗口：聚合窗口从锚点交易起（同一分钟内按 `tx_id` 先后），前向窗口按分钟取 `(t, t+W]`；多个窗口都命中时取代表窗口，并列取最早的。`detail` 中的时间写完整的 `YYYY-MM-DD HH:MM`（样例 fixture 只写了 `HH:MM`，措辞不作为契约）。（甲）
- 工单：状态为“证据不足”且账户在链上时，`conclusion` 在模板前加“该账户在资金链 {chain_id} 中表现为{role}，”，以满足“在链上时必须包含 chain_id”。`supporting_evidence` 先放本账户在主链上的边，再用风险规则证据补足，最多 10 条，按时间升序（避免规则证据多时挤掉链上的边）。（甲）
- 工单落盘目录默认 `tickets/`，可用环境变量 `FUNDTRACE_TICKET_DIR` 修改（测试用临时目录）。（甲、乙）
- `rejudge` 的 `reason`：同一条链上只有角色变化时，链变化片段写“在资金链 {chain_id} 中的角色由{旧}变为{新}”。“新命中”括号中的变化说明取自 `rules_diff` 的 changed（参数、`in_types`/`out_types`、等级都会写出，参数去掉 `params.` 前缀）。（甲）
- `02_规则规范.md` 5.3 节同步写入 `max_hops` 的放宽规则。（甲）

## 1.0.1 — 2026-10-29（只补充实现细则，字段不变）

`core/api.py` 的 `get_account`、`get_transactions` 实现时对 03 规范第 1、2 节未写明处的取舍，乙的 `server.py` 与提示词按此对接：

- 账户号先去首尾空白并转大写，再校验 `^A\d{4,}$`。格式不合法返回 `BAD_PARAM`；格式合法但不存在返回 `ACCOUNT_NOT_FOUND`。（甲、乙）
- `start`/`end` 为 `None` 或空串表示不限；非 `YYYY-MM-DD HH:MM` 或不是真实时间返回 `BAD_TIME_FORMAT`；`start` 晚于 `end` 返回 `BAD_PARAM`。返回对象里的 `start`、`end` 为规范化后的值或 `null`。（甲、乙）
- `limit` 为 `None` 时取默认 50；非整数（含布尔、字符串）或不在 1 至 200 返回 `BAD_PARAM`。（甲、乙）
- 范围内无交易不是错误，返回 `total=0, count=0, truncated=false, transactions=[]`。（甲、乙）
- 接口确认记录：2026-10-30，甲、乙两人已按本文件与 `03_判定与输出规范.md` 第 1、2 节对齐，接口、枚举、版本口径确认无异议。（甲、乙）

## 1.0.0 — 2026-10-29

首次发布规范。下面列出相对开发指南、任务书中**旧约定**的所有改动。代码请按本版本实现。

### 新增

- 机器可读规范：`enums.yaml`、`data_schema_v1.yaml`、`rules/rules_v1.yaml`、`rules/rules_v2.yaml`、`gen_profile_v1.yaml`、`schemas/*.schema.json`。
- `dataset_meta.json`：记录 dataset_id、seed、time_range、row_counts、两个 CSV 的 sha256；校验器会核对这些值。（甲）
- `validate_spec.py`：校验数据、答案、fixtures、工单，并扫描防泄题；内含追链参考实现和 `--print-diff`。（甲、乙）
- `examples/`：一套最小数据集（10 个账户、9 笔交易），以及与之一致的 7 个 fixtures。乙可直接复制到 `core/fixtures/`。（乙）
- 枚举值均有英文 code。工单、rejudge 新增 `status_code`；严重度为 CLEAR 0 < RISK_SIGNAL 1 < INSUFFICIENT 2 < REVIEW 3。（乙）
- 错误返回统一为 `{error, code, detail}`，错误码有 ACCOUNT_NOT_FOUND、BAD_RULE_VERSION、BAD_TIME_FORMAT、BAD_PARAM、INTERNAL。（甲、乙）
- 缺口代码新增 `GAP_BIZ`：反向证据非空时必须列出。（甲）
- 外部数据（AMLSim）的接入原则见 `01_数据规范.md` §8.1；交易表增加可选列 `src_ref`。（甲）

### 变更（接口）

- `get_transactions` 的返回值由列表改为对象：`{acct_id, start, end, total, count, truncated, transactions[...]}`。键名为 **`transactions`**，不是 `items`。每条交易增加 `direction`（转入/转出）。（甲、乙）
- `missing_evidence` 由字符串列表改为对象列表 `[{code, desc}]`，**第一项必须是 GAP_KYC**。（甲、乙）
- 工单字段确定为：`ticket_id`（`TK-<版本>-<账户>`）、`spec_version`、`status_code`、`supporting_evidence[{tx_id, desc}]`、`counter_evidence[{rule_id, rule_name, desc, tx_ids}]`、`rule_basis[{rule_id, rule_name, aligned_to}]`（按 rule_id 升序）。（甲、乙）
- `rejudge` 的 changed 项增加 `direction`、`old/new_role`、`old/new_chain_id`、`rule_changes{added, removed}`、`reason`（按模板拼接）。summary 包含 `total, changed, upgraded, downgraded, by_transition`。（甲、乙）
- ID 正则放宽为可变位数：`^A\d{4,}$`、`^T\d{5,}$`、`^L-T\d{5,}$`、`^TK-v\d+-A\d{4,}$`、`^C\d{2,}$`。乙的 `check_ids.py` 要改用 `T\d{5,}`。（乙）
- 规则文件路径固定为 `Data and Rules/rules/rules_{version}.yaml`。（甲、乙）

### 变更（规则口径）

- 参数统一改名：时间窗一律用 `window_min`（分钟）；比例用 `ratio_min` / `ratio_max`。旧名 `out_ratio`、`out_ratio_max`、`window_hours` 作废。（甲）
- **R02** 改为"短时多来源集中转入"，参数 `window_min: 60, min_sources: 3`（旧为 24 小时窗口）。依据是蒙特卡罗模拟（各 20 次）：24 小时窗口下有 55–120 名普通个人命中；改为 60 分钟后约 2 人命中，5 家高频商户仍全部命中。（甲）
- **R11**（v2）改为 `multi_first_cp`：1440 分钟内 ≥2 个首次对手、每笔 >10000 元。参数名为 `window_min, min_counterparties, amount`（旧名 `window_hours, min_victims` 作废）。（甲）
- R03 增加 `min_total: 20000`，`max_single` 改为 9999（每笔 ≤9999）。（甲）
- R05 的开户天数以 `dataset_meta.time_range[0]` 为基准日。（甲）
- 状态判定增加"复核"分支：|H| ≥ 2、在链上、角色为一级收款端/中转端/拆分端时 → 建议人工复核。H 包含 R07 和 R11。（甲）
- 角色判定按顺序：无 → 疑似受骗付款端 → 末端 → 拆分端 → 一级收款端 → 中转端，在主链上判定。（甲）

### 修复

- **追链算法**：旧版"两阶段遍历"（从种子交易分别向上、向下递归）会把同一账户不相关的转入、转出拼在一起，例如把 C05 停留 100 分钟的链在 v1 下误识别为一条链。新定义改为**链接图**：e1→e2 成立需满足 e1.to == e2.from、e1.t < e2.t ≤ e1.t+W，且向下、向上两侧都满足 0.5 倍守恒；链取链接图的弱连通分量。`max_hops` 只裁剪返回的边，标记 `truncated`。详见 `02_规则规范.md`。参考实现在 `validate_spec.py` 的 `reference_chains`。（甲）

### 变更（仿真数据，`gen_profile_v1.yaml`）

- 个人互转保持约 1400 笔。原先"降到 0.4 笔/人/天"的计划作废（R02 改为 60 分钟窗口后已不需要）。
- 高频商户：每天 30–34 笔、10–300 元，同一天内付款方不重复。总量约 2930 笔背景交易，加上链约 3000 笔（旧文档写的"约 1050 笔高频消费"和"2800–2950"作废）。
- 受骗方每人转出 25000–50000 元；快进快出的转出比例为 0.96–1.0。
- 时间：链的首笔交易在 8–17 点（C03 例外：01:00–02:30 开始，04:00 前结束）；v1 能检出的链从首笔转入到转出 ≤55 分钟；C05、C06 停留 70–100 分钟（v2 才能检出）。
- 链上账户：前后各 180 分钟静默期；对手须是首次对手；一个账户只属于一条链；约 1/3 的末端追加一笔提现到 CASH。
- **D3**：F→P 10500 元（03-04 14:00），P→L 9800 元（15:30），比例 0.933。v2 下 R01 命中、R04 不命中。P 另有一笔来自第二家企业的工资，该企业在答案表中登记为"工资"。
- 预期 v1→v2 的变化：C05/C06 一级收款端 RISK_SIGNAL→REVIEW；其受骗端 CLEAR→RISK_SIGNAL；D3 的 P CLEAR→INSUFFICIENT，F、L CLEAR→RISK_SIGNAL（v2 中 F→P→L 成链）。
- 误报分母为 59（1 家工资企业 + 28 名纯员工 + 30 家商户），做 D3 时为 63。背景账户的告警单独统计。

### 补充（第 2 天埋链实现时，增量变更，版本号不变）

- `gen_profile_v1.yaml` 的 `chain_common` 新增两个键（甲）：
  - `quiet_scope: natural_day`：静默期在“首笔前、末笔后各 180 分钟”之外，再扩大到链路所在自然日的全天（D3 同样适用）。原因：R04 按自然日统计出入比（≥ 0.95），只按 180 分钟静默时，当天其他时段混入约 1000 元背景转入就会让一级收款端的 R04 失效。
  - `r02_guard: true`：v2 演示链（C05、C06）的受骗方和 D3 的 F、P、L，背景转入不得在 60 分钟内凑满 3 个来源（参数取 `rules_v1` 的 R02），保证它们的 v1 预期“未见异常”不随 seed 漂移。
- 首次对手的口径明确为：同一条链上**任意两个账户**之间，除链上交易外无任何交易（原文“链上每对账户”）。（甲）
- `validate_spec.py --check-leak` 的白名单加入 `verify_injected_chains.py`（甲的埋链核对脚本，需要读 `eval/`）。`01_数据规范.md` 第 1 节、`README.md` 第 3 节同步。（甲）
- 实测（seed 42）：交易 2973 笔（背景 1400 + 1472 + 30、链上转账 57、提现 11、D3 2 笔加 1 笔工资）；答案 132 行（涉诈 69、干扰 63）；v1 追到 10 条、v2 追到 12 条，v2 另有 D3 一条，与 `expectations` 一致。（甲）
