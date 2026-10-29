# ontology/

本体目录，由甲维护。用一份 YAML 描述系统里的概念和关系，让规则、工单、证据之间的依据关系有统一说法。属于加分项，不影响主流程。

## 计划放入的文件

| 文件 | 内容 | 产生时间 |
|---|---|---|
| `tbox_v1.yaml` | 本体 v1 的类与关系 | 第 5 天以后（任务 S1，约 0.5 小时） |

## 内容范围

- 类：Account、Transaction、FundChain、ChainRole、FraudPattern、RiskSignal、Rule、Regulation、Case、Evidence、Ticket。
- 关系：`Rule uses RiskSignal`、`Rule aligned_to Regulation`、`Ticket supported_by Evidence`、`Ticket depends_on Rule@version`。
- 规则 YAML 里的 `aligned_to` 字段对应本体中的 `aligned_to` 关系。

## 注意

- 这里描述的是**概念和关系**，不是具体的账户或交易数据。
- 时间紧时可以不做，不影响数据、规则、工单和 Nexent 对接。
