# 本地复现核验

2026-11-07，Python 3.12.14。

- 工作区已有 91 个测试通过；素材依据 24 条核对通过，敏感扫描 0 处。
- 首次一键核验失败原因：Windows `core.autocrlf=true` 将冻结 CSV 检出为 CRLF；当前运行环境缺少 matplotlib。
- 新增 `.gitattributes` 将 CSV 固定为 LF；只做 CRLF → LF 字节还原，没有重新生成数据或修改字段。还原后 `git diff --exit-code -- data/accounts.csv data/transactions.csv` 为 0，两个 SHA256 与 `data/dataset_meta.json` 一致。
- 依赖安装到被忽略的本地 `_tmp_plotdeps/`，没有修改 requirements.txt 或全局环境。
- 使用 `git -c core.autocrlf=false clone --no-hardlinks . _tmp_checks/release-repro-20261107` 创建隔离检出，覆盖本次 receipt Schema 和新增契约测试后，运行 `python core/run_checks_jia.py`，12/12 全部通过。日志保留在该隔离检出的 `_tmp_checks/run_checks_jia_log.txt`。
- 这是当前机器的隔离检出核验，复用了本机安装的依赖；不等于全新虚拟环境安装验证或云端重新部署。隔离检出中的一键脚本生成产物不覆盖主工作区。
