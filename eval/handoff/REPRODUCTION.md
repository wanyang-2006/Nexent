# 干净环境、打包与数字复现

日期：2026-10-31；Windows，本机 Python 3.14.2。基线提交 785ab90，交付包含本轮未提交补丁，manifest 明确记录 overlay。

## 实际执行结果

| 检查 | 结果与证据 |
|---|---|
| 独立克隆 | `git -c core.autocrlf=false clone --no-hardlinks . _tmp_checks/clean-repro` 成功 |
| 全新虚拟环境 | 新建 .venv，按 requirements.txt 安装全部依赖成功，未用全局 site-packages |
| 干净检出复现 | 在独立 clone 执行完整核验，12/12 通过、86 测试通过 |
| 修复后工作区 | 12/12 通过，87 测试通过；防泄题 0 错误；数据哈希正确 |
| 解压后复现 | 更新修复后的代码包解压 `_tmp_checks/packaged-final`，使用独立 venv，12/12 通过、87 测试通过 |
| MCP 契约 | 独立 venv 执行 mcp_server/test_contract.py，9 测试通过 |
| 资产表复现 | 连续生成 SHA256 均为 8CFFFD4BD58AAE760F30663FA8379D4A4003D5D906D8631F699C951F094D5D62，13 项 |
| 代码与素材 ZIP | CRC、解压逐文件哈希、源码编译、冻结 CSV 哈希及常见明文凭据模式检查通过 |
| 乙方技术 ZIP | 实际运行 agent/handoff/build_delivery.py，91 文件、嵌套 V9 哈希、CSV 哈希、编译及凭据扫描通过 |

日志分别在 `_tmp_checks/run_checks_jia_log.txt`、`_tmp_checks/clean-repro/_tmp_checks/run_checks_jia_log.txt`、`_tmp_checks/packaged-repro/_tmp_checks/run_checks_jia_log.txt`。日志不打入交付包。全局环境有一条第三方 anyio 的 pytest 10 弃用警告，不影响通过；新环境未因此失败。

包名为 `dist/fundtrace-jia-code-data-20261031.zip`、`dist/fundtrace-bing-materials-20261031.zip`、`dist/fundtrace-agent-v9-20261031.zip`。以同目录的 .sha256 和 .verification.json 为准，不在此复制会随文档更新变化的 ZIP 哈希。包在本文件最后更新后再次生成，包含本文件；须对最新包执行所述解压复现。

代码包是离线研发复现包，含答案；生产 MCP 部署仍需按乙方技术包/部署说明排除 eval。没有验证跨系统安装或云端本轮更新。没有把源码编译通过当作已部署成功。
