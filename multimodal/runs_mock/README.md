# runs_mock/

手填的模拟结果，只用于调通 `score.py`（任务分工 J4 验收：“用手填的 3 份模拟结果调通”）。不是智能体的真实输出，不得写入 `results.md`。

- `R01.json`、`U02.json`：按 `schemas/receipt.schema.json` 手填的识别 JSON（U02 收款尾号被遮挡，填 null 并列入 unreadable_fields）
- `summary.csv`：R01、U02 风险档位，X01 注入测试，P04 工单核验（不一致，差异字段 status）

运行：`python multimodal/score.py multimodal/runs_mock`
