# 甲方第 5–7 日技术材料

整理日期：2026-10-31。全部账户和交易为合成数据；公开案例为报道摘要。本目录供丙编写文档、PPT、旁白，不能作为工具运行时输入。

## 材料入口

| 材料 | 仓库路径 | 使用说明 |
|---|---|---|
| 数据来源与生成 | data/README.md | 300 账户、2973 交易、12 条埋入链、三类干扰 |
| 规则及差异 | kb/rules_v1.md、rules_v2.md、rules_diff_v1_v2.md | 阈值是仿真内部规则 |
| 方法与代码解读 | eval/handoff/METHOD.md | 三段关键代码，每段不超过 20 行 |
| 评测、基线 | eval/result.md、eval/baseline.md | 数字唯一来源，不能混淆链覆盖与系统链总数 |
| 数字核对表 | eval/handoff/NUMBERS.md | 文档和旁白逐项核对 |
| 链路图 | eval/graphs/ | v1 两张、v2 两张；节点颜色表示角色 |
| 本体 | ontology/tbox_v1.yaml | 概念和关系，不是个人真实画像 |
| 资产登记 | eval/assets_manifest.csv | 13 项，案例注明出处和改写 |
| 演示与失败边界 | agent/handoff/DEMO.md、eval/handoff/REVIEW.md | V9 不等于规则 v9；业务规则仅 v1、v2 |
| PPT制作说明 | agent/handoff/丙_校赛PPT制作说明.md | 14页建议结构、演示串联和审稿清单 |

## 可复现交付

在仓库根目录运行 `python core/build_jia_delivery.py`。`dist/` 生成代码数据包和给丙的材料包，各有 SHA256、文件清单和验证结果；材料包包含 `agent/handoff/丙_校赛PPT制作说明.md`，不含答案 CSV。代码包保留 eval 供离线评测，但部署 MCP 时不得复制 eval。

## 对外表述

使用“在本作品设定的仿真场景内”。v2 演示链专门设计，用于说明规则变化，不证明真实环境泛化。案例 02、03 上游并非纯电诈。公开案例不是当前账户的证据。

当前仓库没有丙的最终文档、PPT 和视频，因此不能声称已逐页或逐帧验收。请依 NUMBERS.md 填写；最新截图和视频仍是乙丙待完成项。材料整理完成与对方确认收到是不同状态，不代签接收人。
