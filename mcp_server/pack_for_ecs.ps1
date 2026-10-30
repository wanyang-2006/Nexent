# 为已有 ECS Python 虚拟环境生成代码与合成数据更新包；Python 依赖不打入包内。
# 用法（在仓库根目录打开 PowerShell，先运行过 install_win.ps1）：
#   powershell -ExecutionPolicy Bypass -File mcp_server\pack_for_ecs.ps1 -PyVersion 3.10
#   -PyVersion  必填：ECS 上 python3 --version 的前两段，如 3.10、3.11、3.12
#   -Arch       ECS 上 uname -m 的结果：x86_64（默认）或 aarch64
# 输出：mcp_server\dist\fundtrace_mcp.tar.gz（dist 已加入 .gitignore，不会提交）
param(
  [Parameter(Mandatory = $true)][ValidatePattern('^3\.\d+$')][string]$PyVersion,
  [ValidateSet("x86_64", "aarch64")][string]$Arch = "x86_64",
  [string]$FastmcpVersion = "4.1.4",
  [string]$PythonExe
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
function Say($m) { Write-Host "`n== $m" -ForegroundColor Cyan }
function Fail($m) { Write-Host "`n[失败] $m" -ForegroundColor Red; exit 1 }

$Vpy = if ($PythonExe) { $PythonExe } else { Join-Path $Root ".venv\Scripts\python.exe" }
if (-not (Test-Path $Vpy)) { Fail "没有找到 Python：$Vpy。用 -PythonExe 指定一个可运行的 Python 3 环境" }
& $Vpy -c 'import sys; print(sys.version.split()[0])'
if ($LASTEXITCODE -ne 0) { Fail "无法运行 $Vpy；请用 -PythonExe 指定一个可运行的 Python 3 环境" }
$Dist = Join-Path $PSScriptRoot "dist"
$Stage = Join-Path $Dist "fundtrace"
if ([IO.Path]::GetFullPath($Stage) -ne [IO.Path]::GetFullPath((Join-Path $Root 'mcp_server\dist\fundtrace'))) { Fail 'Unexpected staging path' }
if (Test-Path $Stage) { Remove-Item $Stage -Recurse -Force -ErrorAction Stop }
New-Item -ItemType Directory -Force -Path (Join-Path $Stage "mcp_server") -ErrorAction Stop | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Stage "core\fixtures"), (Join-Path $Stage "data") -ErrorAction Stop | Out-Null

Write-Host "ECS target: Python $PyVersion, $Arch. Dependencies are not bundled; the existing ECS .venv must already have FastMCP $FastmcpVersion."

# 1. 复制代码，统一转成 LF（install.sh 在 Linux 上遇到 CRLF 会报错）
Say "1/2 复制代码和合成数据"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$files = @(
  @{ Src = "mcp_server\server.py";   Dst = "mcp_server\server.py" },
  @{ Src = "mcp_server\selftest.py"; Dst = "mcp_server\selftest.py" },
  @{ Src = "mcp_server\README.md"; Dst = "mcp_server\README.md" },
  @{ Src = "mcp_server\DEPLOY.md"; Dst = "mcp_server\DEPLOY.md" },
  @{ Src = "mcp_server\SYSTEMD.md"; Dst = "mcp_server\SYSTEMD.md" },
  @{ Src = "mcp_server\UPGRADE_REAL.md"; Dst = "mcp_server\UPGRADE_REAL.md" },
  @{ Src = "mcp_server\install.sh";  Dst = "mcp_server\install.sh" },
  @{ Src = "mcp_server\install_systemd.sh"; Dst = "mcp_server\install_systemd.sh" },
  @{ Src = "mcp_server\requirements.txt"; Dst = "mcp_server\requirements.txt" },
  @{ Src = "core\__init__.py"; Dst = "core\__init__.py" },
  @{ Src = "core\api.py"; Dst = "core\api.py" },
  @{ Src = "core\store.py"; Dst = "core\store.py" },
  @{ Src = "core\trace.py"; Dst = "core\trace.py" },
  @{ Src = "core\rules.py"; Dst = "core\rules.py" },
  @{ Src = "core\ruleset.py"; Dst = "core\ruleset.py" },
  @{ Src = "core\ticket.py"; Dst = "core\ticket.py" },
  @{ Src = "core\rejudge.py"; Dst = "core\rejudge.py" },
  @{ Src = "Data and Rules\enums.yaml"; Dst = "Data and Rules\enums.yaml" },
  @{ Src = "Data and Rules\rules\rules_v1.yaml"; Dst = "Data and Rules\rules\rules_v1.yaml" },
  @{ Src = "Data and Rules\rules\rules_v2.yaml"; Dst = "Data and Rules\rules\rules_v2.yaml" },
  @{ Src = "requirements.txt";       Dst = "requirements.txt" }
)
foreach ($f in $files) {
  $sourcePath = Join-Path $Root $f.Src
  $destPath = Join-Path $Stage $f.Dst
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destPath) | Out-Null
  $text = [System.IO.File]::ReadAllText($sourcePath) -replace "`r`n", "`n"
  [System.IO.File]::WriteAllText($destPath, $text, $Utf8NoBom)
  Write-Host "  $($f.Dst)"
}
Get-ChildItem (Join-Path $Root "core\fixtures\*.json") | Copy-Item -Destination (Join-Path $Stage "core\fixtures")
foreach ($name in @("accounts.csv", "transactions.csv", "dataset_meta.json")) {
  Copy-Item -LiteralPath (Join-Path $Root "data\$name") -Destination (Join-Path $Stage "data\$name")
}

# 2. 打包（Windows 10 1803 及以上自带 tar）。在 dist 目录内用相对路径打包，避开中文路径
Say "2/2 打包"
Push-Location $Dist
try {
  if (Test-Path "fundtrace_mcp.tar.gz") { Remove-Item "fundtrace_mcp.tar.gz" -Force }
  tar -czf fundtrace_mcp.tar.gz fundtrace
  if ($LASTEXITCODE -ne 0) { Fail "tar 打包失败" }
} finally { Pop-Location }
$Tgz = Join-Path $Dist "fundtrace_mcp.tar.gz"
Write-Host ("`n[完成] {0}（{1:N1} MB）" -f $Tgz, ((Get-Item $Tgz).Length / 1MB)) -ForegroundColor Green
Write-Host @"

上传并安装（把 <SSH连接名> 换成 VS Code Remote SSH 使用的 Host 别名）：
  scp mcp_server\dist\fundtrace_mcp.tar.gz <SSH连接名>:~/fundtrace_mcp.tar.gz
  ssh <SSH连接名>
  tar -xzf ~/fundtrace_mcp.tar.gz --strip-components=1 -C ~/fundtrace-mcp
  cd ~/fundtrace-mcp
  .venv/bin/python -m pip install -r mcp_server/requirements.txt
  MCP_MODE=real bash mcp_server/install_systemd.sh
"@
