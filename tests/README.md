# tests/

自动化测试，由甲维护。仓库根目录运行：

```powershell
python -m pytest tests -q
```

依赖：`pytest`、`jsonschema`（>=4.18，自带 `referencing`）。

| 文件 | 内容 |
|---|---|
| `conftest.py` | 把仓库根目录加入 `sys.path`；提供 schema 校验器 `validator`，以及 `real_data`（正式数据 `data/`）、`example_data`（`Data and Rules/examples/data` 样例数据）两个数据夹具；自动把 `make_ticket` 的落盘目录改到临时目录（`FUNDTRACE_TICKET_DIR`），避免测试写进 `tickets/` |
| `test_api_queries.py` | `get_account`、`get_transactions` 的契约与正确性测试，详见 `core/README.md` 的“测试”一节 |
| `test_engine.py` | `trace_chain`、`check_rules`、`make_ticket`、`rejudge`：样例数据上与 fixtures 比对；正式数据上追链与参考实现 `reference_chains` 逐条比对，300 个账户 × v1/v2 的 schema 与工单语义检查，重判自洽，设计预期，错误参数 |

测试可以读 `data/`，不得读答案目录里的文件（仅 `core/evaluate.py`、`selfcheck.py` 可以）。

`test_engine.py` 中的 `test_design_expectations` 检查的是 03 规范第 4 节的设计预期，不是答案。它失败时先看 `eval/selfcheck_v*.txt`，再决定是改规则实现还是更新预期（更新预期要同步 `eval/demo_accounts.md`）。

## 变更记录

- 2026-10-29：新增 `test_engine.py`；`conftest.py` 增加自动夹具 `_tickets_to_tmp`；`test_api_queries.py` 的防泄题检查扩大到全部工具模块。尚未在本机运行。
