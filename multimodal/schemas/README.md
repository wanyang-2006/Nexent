# 凭证字段契约

## 2026-11-07 币种缺省修正

`currency` 为非空字符串或 null。只按材料明确的币种代码/名称映射，例如“人民币”→CNY、“美元”→USD；只有金额或 ¥ 符号不足以唯一判断币种时填 null。取消默认 CNY，避免将样例布局或中国银行背景当作币种证据。该变更允许表达未知值，不允许补造币种，也不改变姓名、账号或风险真值。

历史完整回归在原字符串契约下有四项失败，旧 Schema 原样存于 `../runs/2026-11-07-full-regression/receipt.schema.snapshot.json`，历史 `schema-report.json` 不覆盖。复现历史检查应显式指定：

```bash
python multimodal/validate_run.py multimodal/runs/2026-11-07-full-regression --schema multimodal/runs/2026-11-07-full-regression/receipt.schema.snapshot.json
```

新一轮使用当前 Schema，分开报告契约更新与模型重测，不能把旧结果重新验证后冒称原先通过。

## 语义规则

- 姓名逐字保留掩码，不删星号、不补字。
- 账户类型必须有明确标识，公司名称或个人姓名不能代替类型字段。
- 有字段标签且内容被遮挡/模糊时归入 unreadable_fields；版面没有该字段时归入 not_shown_fields，两者互斥。
- Schema 只能检查结构，不能证明图片识别正确；完整验收同时核对真值、原图、类型依据及字段可见性。

批量保存后可执行 `python multimodal/validate_run.py <目录> --semantics`，在 Schema 以外检查样例姓名/账户类型真值、不可读分类、两种缺失数组互斥及卡类型误填银行。该检查不会修改输出；当前只覆盖列明的语义，不能替代金额、时间及全文人工核对。
