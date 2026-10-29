# MCP 开机自启与进程守护

适用：Linux 云服务器，systemd 已运行，项目在 `/home/Liu/fundtrace-mcp`，虚拟环境及 hybrid 部署文件已安装。
安装结果：服务名 `fundtrace-mcp.service`，以当前普通用户运行，开机启动、进程退出后5秒自动重启；日志写入 journal。
该机制恢复进程退出，不检测进程仍存活但无法响应的情况。手动 systemctl stop 后不会自动重启。
新版安装脚本将运行模式设为 hybrid：账户/交易查询读取完整合成数据集，其他五个分析工具仍使用固定 fixture。服务仍使用 SSE、0.0.0.0:8900，Nexent 地址不变。不会安装 Python 依赖或自动修改防火墙。

## 1. 上传新版部署包

必须先上传包含新版 MCP、core、fixtures、data 的完整部署包，不能只上传 `install_systemd.sh`。本机 PowerShell 先按 `pack_for_ecs.ps1` 制作 Linux 包，再上传；将 SSH 连接名替换为 VS Code 使用的 Host 别名：

```powershell
scp "D:\ICT开发者乙任务\GithubClone\Nexent\mcp_server\dist\fundtrace_mcp.tar.gz" 你的SSH连接名:~/fundtrace_mcp.tar.gz
```

远程终端执行以下命令，将包内容覆盖到现有项目目录（保留 `.venv` 和 systemd 服务）：

```bash
tar -xzf ~/fundtrace_mcp.tar.gz --strip-components=1 -C ~/fundtrace-mcp
```

## 2. 停止旧的 nohup 服务

远程终端执行：

```bash
sudo ss -lntp 'sport = :8900'
```

记下输出的 pid，用实际数字替换 PID，再核实命令：

```bash
ps -fp PID
```

确认是该项目的 Python MCP 服务后执行 `kill PID`（普通用户停止自己启动的旧进程），随后再次检查端口。
若不是该项目进程，先查明占用原因，不要停止未知进程。
安装脚本发现端口被占且 systemd 服务未运行时会中止，不会自动杀进程。
不要同时用 nohup 和 systemd 启动同一端口的 MCP。

## 3. 安装

以 Liu 用户在远程终端执行，不要在整个脚本前加 sudo：

```bash
cd ~/fundtrace-mcp
bash mcp_server/install_systemd.sh
```

脚本在需要安装系统服务时请求 sudo，先自检，再写入 `/etc/systemd/system/fundtrace-mcp.service`。
输出应包含 `PASS: 8 tools; 18 MCP calls ...`、`enabled`、`active`。安装前需先部署包含 `core/`、`data/` 的新版包；缺少数据时自检会失败，旧进程不会被自动杀掉。
若出现 `\r` 或 `pipefail` 等换行错误，先执行 `sed -i 's/\r$//' mcp_server/install_systemd.sh` 再运行。

## 4. 检查与管理

```bash
sudo systemctl status fundtrace-mcp --no-pager
sudo systemctl is-enabled fundtrace-mcp
sudo systemctl is-active fundtrace-mcp
sudo journalctl -u fundtrace-mcp -n 50 --no-pager
```

更新代码后：`sudo systemctl restart fundtrace-mcp`。
停止：`sudo systemctl stop fundtrace-mcp`。
停止并取消开机启动：`sudo systemctl disable --now fundtrace-mcp`。

断开 SSH、重新连接后运行 `MCP_MODE=hybrid .venv/bin/python mcp_server/selftest.py http://127.0.0.1:8900/sse`，验证退出终端后服务仍能访问且按 hybrid 结果验收。
不需要为本次安装立刻重启云服务器；以后计划重启时，再验收开机后 active 和协议测试。
回到 Nexent 刷新 fundtrace，确认连接成功并做一次智能体问答。

## 5. 后续完整真实算法

只有甲完成追链、规则、工单、重判 API 并验收后，才将 unit 改为 `MCP_MODE=real`。当前 core.api 只有账户、交易查询；hybrid 中其余工具仍是固定 A0087/v1 样例。切换前确认所有七个业务 API、所需规则和数据文件已部署，并通过对应测试。

如确需临时手动设置，可用 `sudo systemctl edit fundtrace-mcp` 添加：

```ini
[Service]
Environment=MCP_MODE=real
```

然后执行 `sudo systemctl daemon-reload`、`sudo systemctl restart fundtrace-mcp`，并使用真实后端对应测试。
现有 selftest.py 是 fixture 专用断言，不能用来证明真实后端输出正确。
service 的环境变量与终端 export 独立；修改终端变量不会自动修改已运行的 systemd 服务。
