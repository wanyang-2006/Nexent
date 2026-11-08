核验结论：一致

系统记录与上传工单 PDF 在所有可核对字段上完全一致，没有差异。

只读来源
系统对照记录来自只读工具 get_ticket(acct_id="A0209", rule_version="v1")
本流程未生成、未覆盖、未修改任何工单（未调用 make_ticket）
字段对照表
字段	PDF 值	系统值	是否一致
工单编号	TK-v1-A0209	TK-v1-A0209	一致
账户编号	A0209	A0209	一致
规则版本	v1	v1	一致
状态	建议人工复核	建议人工复核（status_code=REVIEW）	一致
角色	中转端	中转端	一致
链路编号	L-T01908	L-T01908	一致
结论表述	账户在 L-T01908 中为中转端，命中 R01、R04、R07、R08，建议人工复核	同一表述	一致
命中规则	R01、R04、R07、R08	R01、R04、R07、R08	一致
缺失证据代码	GAP_KYC、GAP_MEMO_DEVICE、GAP_CALLBACK、GAP_HISTORY	同四项	一致
驳回证据	未提供	counter_evidence 为空数组（系统无内容）	系统记录未提供可比较内容，不判定
spec_version	未展示	1.0.0	系统记录未提供（PDF 无此字段）
证据编号差异
共同交易编号（5 条，完全一致）：T01908、T01913、T01932、T01938、T01942
PDF 独有：无
系统独有：无
缺失证据代码同样无差异：GAP_KYC、GAP_MEMO_DEVICE、GAP_CALLBACK、GAP_HISTORY

注：交易编号按集合比对，编号本身不用于推断金额或交易先后关系。

数据性质与限制
工具返回 _demo.mode = synthetic_dataset，backend_mode = real，数据集为 sim-gen_profile_v1-seed42：结果基于完整合成数据集及 v1 规则计算，不是真实银行数据，也不是固定样例。
PDF 标注为“仿真数据”，与系统数据性质相符。
本次仅比对工单字段与支持证据编号；金额、对手方关系、命中规则的判定过程未逐项复算，如需复核规则计算逻辑可另行指定。
该核验只证明 PDF 与系统记录一致，不构成对账户涉诈事实的认定。
