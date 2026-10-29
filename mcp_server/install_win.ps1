# 本机（Windows）安装 fastmcp 并启动 fundtrace MCP 服务，然后自检。可重复执行。
# 用法（在仓库根目录打开 PowerShell）：
#   powershell -ExecutionPolicy Bypass -File mcp_server\install_win.ps1
# 可选参数：
#   -Full                        同时安装 requirements.txt 全部依赖（pandas 等，第 3 天接甲的代码时用）
#   -Transport streamable-http   改用 streamable-http（地址后缀 /mcp）
#   -Port 8900                   端口
#   -Stop                        只停止服务
# 本机服务只监听 127.0.0.1，用于开发自测；Nexent 接入在 ECS 上做。
param(
  [ValidateSet("sse", "streamable-http")][string]$Transport = "sse",
  [int]$Port = 8900,
  [string]$FastmcpVersion = "4.1.4",
  [switch]$Full,
  [switch]$Stop
)
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$PidFile = Join-Path $PSScriptRoot ".pid"
$env:PYTHONUTF8 = "1"

function Say($m) { Write-Host "`n== $m" -ForegroundColor Cyan }
function Fail($m) { Write-Host "`n[失败] $m" -ForegroundColor Red; exit 1 }
function Stop-Mcp {
  if (Test-Path $PidFile) {
    $old = Get-Content $PidFile | Select-Object -First 1
    if ($old) { & taskkill.exe /PID $old /T /F 2>&1 | Out-Null }   # venv 的 python.exe 会再启动一个子进程，按进程树结束
    Remove-Item $PidFile -Force
    Start-Sleep -Seconds 1
  }
}

if ($Stop) { Stop-Mcp; Write-Host "已停止 fundtrace MCP 服务"; exit 0 }

# 1. Python：优先 py 启动器（取已装的最新 3.x），其次 python
Say "1/5 检查 Python"
$PyExe = $null; $PyArgs = @()
if (Get-Command py -ErrorAction SilentlyContinue) { $PyExe = "py"; $PyArgs = @("-3") }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $PyExe = "python" }
else { Fail "没有找到 Python。请从 python.org 安装 3.11 及以上版本，安装时勾选 Add python.exe to PATH" }
$ver = & $PyExe @PyArgs -c "import sys; print('%d.%d' % sys.version_info[:2])"
if ($LASTEXITCODE -ne 0 -or -not $ver) { Fail "无法运行 ${PyExe}。若弹出微软商店，请在 设置 > 应用 > 高级应用设置 > 应用执行别名 里关闭 python.exe 别名" }
$parts = "$ver".Trim().Split(".")
if ([int]$parts[0] -lt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -lt 10)) { Fail "Python $ver 太旧，fastmcp 需要 3.10 及以上" }
Write-Host "使用 ${PyExe} ${PyArgs}（Python ${ver}）"
$ge311 = ([int]$parts[0] -gt 3) -or ([int]$parts[1] -ge 11)
if ($Full -and -not $ge311) { Fail "-Full 要装 pandas 3.0.0，需要 Python 3.11 及以上，当前 $ver" }

# 2. 虚拟环境（仓库根目录 .venv，已有就复用）
Say "2/5 虚拟环境 .venv"
$Vpy = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Vpy)) {
  & $PyExe @PyArgs -m venv .venv
  if ($LASTEXITCODE -ne 0) { Fail "创建 venv 失败" }
}
if (-not (Test-Path $Vpy)) { Fail "venv 里没有 $Vpy，删除仓库根目录的 .venv 后重新运行" }
& $Vpy --version

# 3. 安装
Say "3/5 安装 fastmcp==$FastmcpVersion"
& $Vpy -m pip install -q --upgrade pip
if ($Full) { & $Vpy -m pip install -q -r requirements.txt }
else { & $Vpy -m pip install -q "fastmcp==$FastmcpVersion" }
if ($LASTEXITCODE -ne 0) { Fail "pip 安装失败。网络慢时先执行：`$env:PIP_INDEX_URL='https://pypi.tuna.tsinghua.edu.cn/simple'，再重新运行本脚本" }
& $Vpy -c "import fastmcp; print('fastmcp', fastmcp.__version__)"

# 4. (重新)启动服务，后台运行，日志写到仓库根目录
Say "4/5 启动服务（${Transport}，127.0.0.1:${Port}）"
Stop-Mcp
$busy = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($busy) {
  $pname = (Get-Process -Id $busy.OwningProcess -ErrorAction SilentlyContinue).ProcessName
  Fail "端口 $Port 已被占用（PID $($busy.OwningProcess) $pname）。结束该进程，或加参数 -Port 8901"
}
$env:MCP_TRANSPORT = $Transport
$env:MCP_PORT = "$Port"
$env:MCP_HOST = "127.0.0.1"
$OutLog = Join-Path $Root "mcp.log"
$ErrLog = Join-Path $Root "mcp.err.log"
$proc = Start-Process -FilePath $Vpy -ArgumentList "mcp_server\server.py" -WorkingDirectory $Root `
  -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog -WindowStyle Hidden -PassThru
if (-not $proc) { Fail "启动服务失败" }
Set-Content -Path $PidFile -Value $proc.Id
Write-Host "PID $($proc.Id) ，日志 mcp.log、mcp.err.log"

# 5. 自检：用 MCP 客户端真正调用一次 hello（最多等 15 秒）
Say "5/5 自检"
if ($Transport -eq "sse") { $Suffix = "/sse" } else { $Suffix = "/mcp" }
$Url = "http://127.0.0.1:$Port$Suffix"
& $Vpy mcp_server\selftest.py $Url
if ($LASTEXITCODE -ne 0) {
  if (Test-Path $ErrLog) { Get-Content $ErrLog -Tail 20 }
  Fail "自检失败，见上面的日志（mcp.err.log）"
}

Write-Host "`n[完成] 本机 MCP 服务在运行：$Url" -ForegroundColor Green
Write-Host "停止：powershell -ExecutionPolicy Bypass -File mcp_server\install_win.ps1 -Stop"
Write-Host "打包给 ECS：powershell -ExecutionPolicy Bypass -File mcp_server\pack_for_ecs.ps1 -PyVersion <ECS 的 Python 版本，如 3.10>"
