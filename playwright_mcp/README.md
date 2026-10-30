# playwright_mcp/

让 Claude 通过浏览器查看和操作服务器上的 Nexent 页面（`@playwright/mcp`）。这个目录只放安装脚本和说明，不放任何账号、密码或 Cookie。

## 文件

| 文件 | 作用 |
|---|---|
| `setup_playwright_mcp.ps1` | 检查 Node.js（需 18 或更新）、读取最新版本并固定、检查服务能启动、创建浏览器配置目录、生成配置片段；可选直接合并进 Claude 的配置文件 |
| `claude_config_snippet.json` | 运行脚本后生成。里面是要加到 Claude 配置的 `playwright` 条目（含 Nexent 地址，不含密码） |

## 使用

在 `D:\NexentFile` 下打开 PowerShell（普通用户，不要用管理员）：

```powershell
powershell -ExecutionPolicy Bypass -File playwright_mcp\setup_playwright_mcp.ps1 -NexentUrl "http://<ECS公网IP>:<Nexent网页端口>"
```

要自动写入 Claude 的配置文件，加上 `-ConfigPath "<路径>"`。路径可在 Claude 桌面端的“设置 → 开发者 → 编辑配置”里看到。脚本会先备份成 `.bak`。不加这个参数时，把生成的片段手工合并到配置文件的 `mcpServers` 里。

写入后**完全退出并重启** Claude 桌面端，再开新会话。

## 关键参数的含义

| 参数 | 作用 |
|---|---|
| `--browser msedge` 或 `chrome` | 直接用本机已装的浏览器，不需要另外下载 |
| `--user-data-dir %LOCALAPPDATA%\playwright-mcp-profile` | 保存 Nexent 的登录状态。放在仓库之外，避免 Cookie 被提交到 git；第一次打开浏览器时由你自己登录，密码不经过对话 |
| `--allowed-origins <Nexent地址>` | 只允许浏览器访问 Nexent。官方文档说明它**不是安全边界**，只是减少误访问 |
| 不加 `--headless` | 默认弹出可见窗口，你能看到 Claude 的每一步操作；加 `-Headless` 可改为后台运行 |

## 注意

- 浏览器里的网页内容会被 Claude 读取。Nexent 页面里如果出现指令性文字，Claude 会先向你说明，不会直接照做。
- 不要在对话里发送 Nexent 的账号和密码；登录由你在弹出的窗口里完成。
- 不要把 `playwright-mcp-profile` 目录复制进仓库。
- 访问的是 Nexent 的网页地址，不是 MCP 的内网地址 `172.19.25.141:8900`（那个只给 Nexent 后端用）。

## 变更记录

- 2026-10-30（三）：发现 `claude_desktop_config.json` 只管桌面端聊天（Chat/Cowork），Code 标签页里的 Claude Code 读不到，必须用 `claude mcp add --scope user` 注册（写进 `C:\Users\yang\.claude.json`）。已在本机装好 `@playwright/mcp@0.0.83`，`--help` 运行正常，浏览器用本机 Chrome。在 Git Bash 里执行注册命令时，要加 `MSYS_NO_PATHCONV=1`，否则参数 `/c` 会被改成 `C:/`，导致连接超时。在 PowerShell 里要写 `claude.cmd mcp add ...`，不能写 `claude mcp add ...`：`claude` 会运行 `claude.ps1`，PowerShell 会把 `--` 吞掉，报 `unknown option '-y'`。

- 2026-10-30（二）：首次运行遇到两个问题，脚本已处理。① 网址写成了 `http://:http://…`，脚本现在会先校验网址格式；② npm 默认缓存 `D:\NodeJs\node_cache` 报 EPERM，脚本改用 `%LOCALAPPDATA%\npm-cache-playwright`，并把它写进生成配置的 `env`（Claude 以后启动 playwright 时也走这个缓存）；写入 Claude 配置时改为不带 BOM 的 UTF-8。
- 本机 Claude 配置文件路径：`C:\Users\yang\AppData\Local\Claude-3p\claude_desktop_config.json`。
- 2026-10-30：新增本目录与安装脚本。**脚本编写时无法在本机运行，未经验证**，以你本机运行的结果为准。
