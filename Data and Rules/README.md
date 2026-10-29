# Data and Rules：数据与规则规范（spec_version 1.0.0）

本目录是数据格式、规则口径、判定逻辑和工具输出的**唯一权威来源**。甲乙两份开发指南和任务书里只保留摘要和指向本目录的链接，具体数值以本目录为准。

## 1. 权威顺序

内容冲突时按以下顺序取用（排在前面的优先）：

1. 机器可读文件：`enums.yaml`、`data_schema_v1.yaml`、`rules/rules_v*.yaml`、`gen_profile_v1.yaml`、`schemas/*.schema.json`
2. 规范说明：`01_数据规范.md`、`02_规则规范.md`、`03_判定与输出规范.md`
3. 样例：`examples/`（必须能通过 `validate_spec.py` 校验，否则视为样例有误）
4. 其他文档：开发指南、任务书

YAML 与 md 不一致时，以 YAML 为准，并修正 md。

## 2. 文件索引

| 路径 | 内容 | 主要使用者 |
|---|---|---|
| `01_数据规范.md` | 账户表、交易表、dataset_meta、答案表的字段与约束，以及 AMLSim 等外部数据的接入方式 | 甲 |
| `02_规则规范.md` | R01–R11 的口径、参数、证据选取方式和版本差异；追链（链接图）定义 | 甲、乙 |
| `03_判定与输出规范.md` | 角色、状态、严重度判定；6 个工具的输入输出、工单、rejudge、错误码 | 甲、乙 |
| `enums.yaml` | 枚举（中文值与英文 code 对照）、ID 正则、规则实现名、结论禁用词、特殊 ID | 全部 |
| `data_schema_v1.yaml` | CSV 格式、列定义、跨表约束、交易类型与双方类型的对应关系 | 甲 |
| `rules/rules_v1.yaml`、`rules/rules_v2.yaml` | 规则参数与追链参数 | 甲（core）、乙（展示） |
| `gen_profile_v1.yaml` | 仿真数据的生成参数：12 条链 C01–C12、干扰项 D1–D3、预期结果 | 甲 |
| `schemas/` | 工具返回值、错误、dataset_meta、规则文件的 JSON Schema（Draft 2020-12） | 乙、甲 |
| `examples/data/` | 10 个账户、9 笔交易的最小数据集和 dataset_meta | 两人 |
| `examples/eval/` | 对应的答案表 | 甲 |
| `examples/fixtures/` | 6 个工具及错误返回的标准样例，与 `examples/data` 一致 | 乙 |
| `validate_spec.py` | 校验器，内含追链参考实现和规则差异计算 | 两人 |

## 3. 常用命令

在仓库根目录 `D:\NexentFile` 下运行（目录名含空格，路径要加引号）：

```powershell
# 校验规范本身和 examples（每次改动本目录后都要跑）
python "Data and Rules/validate_spec.py"

# 校验甲生成的数据集和答案
python "Data and Rules/validate_spec.py" --data data --eval eval

# 校验乙的 fixtures（同时给出 --data 时，会检查其中的 ID 是否存在于数据中，并与参考追链结果比对）
python "Data and Rules/validate_spec.py" --data data --fixtures core/fixtures

# 校验批量生成的工单
python "Data and Rules/validate_spec.py" --data data --tickets tickets/v1

# 防泄题：检查 core/ 和 mcp_server/ 中的代码是否读取了 eval/
#（evaluate.py、selfcheck.py、gen_data.py、import_amlsim.py 允许引用，不扫描）
python "Data and Rules/validate_spec.py" --skip-spec --check-leak core mcp_server

# 打印 v1 到 v2 的规则差异（rejudge 的 rule_changes 应与此一致）
python "Data and Rules/validate_spec.py" --print-diff v1 v2
```

退出码：0 表示通过，1 表示有错误。依赖：Python ≥ 3.10、pyyaml、jsonschema ≥ 4.18。

乙在接入初期可先把 `examples/fixtures/*.json` 复制到 `core/fixtures/`，等甲的真实接口可用后再切换。

## 4. 代码中的引用方式

```python
ROOT = Path(__file__).resolve().parents[1]          # 按实际层级调整
SPEC = ROOT / "Data and Rules"
rules_path = SPEC / "rules" / f"rules_{version}.yaml"
```

本目录名含空格，**不能作为 Python 包导入**，只能按路径读取文件。

## 5. 版本政策

- `spec_version` 采用语义化版本，当前为 `1.0.0`。每个 YAML 文件、每个工具返回值和工单中都带有该字段。
- 1.x 内只允许**增量变更**：可以新增字段、枚举值、规则、规则版本（如 v3）、错误码。
- 以下属于**破坏性变更**，必须升到 2.0.0，并经甲乙双方同意：字段或参数改名、删除字段、改变字段类型或含义。
- 枚举值不删除，只标 `deprecated: true`。
- `rule_id` 不复用。同一个 `rule_id` 的 `name`、`type`、`impl` 在所有规则版本中保持不变；要改口径时，新增参数或新增规则。
- 规则版本（v1、v2）和 spec_version 相互独立：新增 `rules_v3.yaml` 属于增量变更。

## 6. 变更流程

1. 修改 YAML 或 schema，并同步对应的 md。
2. 如有需要，更新 `examples/`。
3. 运行 `python "Data and Rules/validate_spec.py"`，确认 0 个错误。
4. 在 `CHANGELOG.md` 中记录变更：日期、版本、内容、影响方（甲、乙、文档）。
5. 涉及接口或口径的变更，先通知对方再合并；破坏性变更须双方同意后才能升版本号。
