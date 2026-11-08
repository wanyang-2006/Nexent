核验结论：一致

本次核验使用只读查询 get_ticket(acct_id="A0105", rule_version="v1")，与上传的 ticket_A0105_v1.pdf 进行比对。本轮没有生成、覆盖或修改任何工单。

只读来源
系统记录：get_ticket 返回工单 TK-v1-A0105（账户 A0105，规则版本 v1）
待核验文件：ticket_A0105_v1.pdf（页面标注“涉诈资金链路研判工单（仿真数据）”）

工单编号 TK-v1-A0105 的格式与账户编号 A0105、规则版本 v1 相符，无编号矛盾。

逐项对照表
字段	PDF 值	系统值	是否一致
工单编号 ticket_id	TK-v1-A0105	TK-v1-A0105	一致
账户编号 acct_id	A0105	A0105	一致
规则版本 rule_version	v1	v1	一致
状态 status	未见异常	未见异常	一致
状态码 status_code	PDF 未展示	CLEAR	系统记录未提供可对照值（PDF 无此字段）
角色 role	无	无	一致
链路编号 chain_id	无（None）	null	一致
结论 conclusion	未发现风险规则命中且不在已识别的资金链上	在本数据范围内未发现风险规则命中，也不在已识别的资金链上	一致（表述详略不同，含义相同）
支持证据 supporting_evidence	空	[]	一致
反向证据 counter_evidence	R09「稳定工资收入」，1 笔工资入账（A0162，8094 元），T01736	R09「稳定工资收入」，有 1 笔工资入账（A0162，8094 元），["T01736"]	一致
缺失证据 missing_evidence	GAP_KYC、GAP_BIZ	GAP_KYC（对手方账户的开户与实名信息）、GAP_BIZ（反向证据的业务背景核实）	一致
规则依据 rule_basis	仿真内部规则v1#R09	仿真内部规则v1#R09（R09 稳定工资收入）	一致
建议动作 suggested_actions	空	[]	一致
规范版本 spec_version	PDF 未展示	1.0.0	系统记录未提供可对照值（PDF 无此字段）
证据编号差异
共同编号：T01736
PDF 独有编号：无
系统独有编号：无

证据编号按集合比对，未依据编号顺序推断金额或交易关系。

数据性质与限制
系统返回 _demo.mode = synthetic_dataset、backend_mode = real、dataset_id = sim-gen_profile_v1-seed42：这是基于完整合成数据集及 v1 规则计算的结果，不是真实银行数据，也不是固定 fixture 样例（与 PDF 标注“仿真数据”相符）。
以下内容在工具返回中没有对应字段或 PDF 未展示，因此不推断为一致：status_code（PDF 未展示）、spec_version（PDF 未展示）。
本次核验仅证明 PDF 内容与系统当前记录在已列字段上相符，不代表交易真实发生，也不构成违法或诈骗认定。
