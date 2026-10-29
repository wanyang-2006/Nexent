# tests/

自动化测试，由甲维护。仓库根目录运行：

```powershell
python -m pytest tests -q
```

依赖：`pytest`、`jsonschema`（>=4.18，自带 `referencing`）。

| 文件 | 内容 |
|---|---|
| `conftest.py` | 把仓库根目录加入 `sys.path`；提供 schema 校验器 `validator`，以及 `real_data`（正式数据 `data/`）、`example_data`（`Data and Rules/examples/data` 样例数据）两个数据夹具 |
| `test_api_queries.py` | `get_account`、`get_transactions` 的契约与正确性测试，详见 `core/README.md` 的“测试”一节 |

后续随 `trace_chain`、`check_rules`、`make_ticket`、`rejudge` 的实现，在此目录追加对应测试。测试可以读 `data/`，不得读答案目录里的文件（仅 `core/evaluate.py`、`selfcheck.py` 可以）。
