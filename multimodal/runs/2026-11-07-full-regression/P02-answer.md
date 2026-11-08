核验结论：一致

上传工单 ticket_A0105_v1.pdf 中可读出的各项字段与系统记录之间未发现差异。

只读来源：本轮仅调用只读工单工具 get_ticket(acct_id="A0105", rule_version="v1")，没有生成、修改或覆盖任何工单。

逐项对照表
字段	PDF 值	系统记录值	是否一致
工单编号	TK-v1-A0105	TK-v1-A0105	一致
账户编号	A0105	A0105	一致
规则版本	v1	v1	一致
状态（原文）	未见异常	未见异常	一致
状态代码	PDF 未展示	CLEAR	系统记录未提供（PDF 未展示，不算差异）
角色	无	无	一致
链路编号 chain_id	空（无）	null	一致
结论	未命中风险规则、不在已识别资金链	在本数据范围内未发现风险规则命中，也不在已识别的资金链上	一致
支持证据 supporting_evidence	空	[]	一致
反向证据 counter_evidence	R09 稳定工资收入；T01736，A0162，8094 元	R09 稳定工资收入；tx_ids ["T01736"]，对手方 A0162，8094 元	一致
缺失证据 missing_evidence	GAP_KYC、GAP_BIZ	GAP_KYC（对手方账户的开户与实名信息）、GAP_BIZ（反向证据的业务背景核实）	一致
规则依据 rule_basis	R09，对齐仿真内部规则 v1#R09	R09，aligned_to 仿真内部规则v1#R09	一致
建议动作 suggested_actions	空	[]	一致
证据编号差异
PDF 独有：无
系统独有：无
共同编号：T01736（反向证据，规则 R09 稳定工资收入）
说明：两侧的支持证据均为空，可比对的交易编号仅有 1 个，且集合完全重合；未按编号顺序推断金额或交易关系。
数据性质与限制
该记录 _demo 标注为 mode=synthetic_dataset、dataset_id=sim-gen_profile_v1-seed42、backend_mode=real，即基于完整合成数据集与指定规则版本的计算结果，不是真实银行数据，也不是固定样例。
PDF 未展示 status_code 字段，该项以表格标注“系统记录未提供”，不推断为一致或不一致。
核验仅代表 PDF 文字与系统记录的一致性，不构成对交易真实性或账户风险的独立认定。
