# Install and configure @playwright/mcp for Claude (Windows PowerShell 5.1 or 7).
# ASCII only on purpose: Windows PowerShell 5.1 misreads UTF-8 without BOM.
#
# Usage (run from D:\NexentFile, normal user, not administrator):
#   powershell -ExecutionPolicy Bypass -File playwright_mcp\setup_playwright_mcp.ps1 -NexentUrl "http://<ECS public IP>:<Nexent web port>"
#
# Optional:
#   -Browser chrome|msedge   default: chrome if installed, otherwise msedge (Windows 11 always has Edge)
#   -ConfigPath "<path to claude_desktop_config.json>"   merge the "playwright" entry into that file (a .bak copy is made first)
#   -Headless                run without a visible window (default: visible, so you can watch and log in)

param(
    [Parameter(Mandatory = $true)][string]$NexentUrl,
    [ValidateSet("chrome", "msedge")][string]$Browser = "",
    [string]$ConfigPath = "",
    [switch]$Headless
)

$ErrorActionPreference = "Stop"

function Fail($msg) { Write-Host "ERROR: $msg" -ForegroundColor Red; exit 1 }

# 0. Validate the URL early (a typo like "http://:http://1.2.3.4:3000" must not get through)
if ($NexentUrl -notmatch '^https?://[A-Za-z0-9.\-]+(:\d+)?(/.*)?$') {
    Fail "NexentUrl looks wrong: $NexentUrl . Expected something like http://60.205.124.241:3000 (one scheme, no placeholder text)."
}

# 0b. Use a private npm cache. The default cache (for example D:\NodeJs\node_cache) may be unwritable (EPERM),
#     which breaks npm view / npx. The same folder is also written into the generated Claude config.
$npmCache = Join-Path $env:LOCALAPPDATA "npm-cache-playwright"
New-Item -ItemType Directory -Force -Path $npmCache | Out-Null
$env:npm_config_cache = $npmCache

# 1. Node.js >= 18
$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) { Fail "Node.js not found. Install Node.js 18 or newer (LTS) from https://nodejs.org, reopen PowerShell, run this script again." }
$nodeVer = (& node --version).TrimStart("v")
if ([int]($nodeVer.Split(".")[0]) -lt 18) { Fail "Node.js $nodeVer is too old, need 18 or newer." }
Write-Host "Node.js $nodeVer"
if (-not (Get-Command npx -ErrorAction SilentlyContinue)) { Fail "npx not found, reinstall Node.js." }

# 2. Latest version of the package (pinned in the generated config so it does not change under you)
$verOut = & npm view "@playwright/mcp" version 2>&1
if ($LASTEXITCODE -ne 0 -or -not $verOut) {
    Write-Host ($verOut | Out-String)
    Fail "npm view failed (see output above). Check network and registry: run 'npm config get registry'. The npmmirror registry normally has this package."
}
$ver = ($verOut | Out-String).Trim()
Write-Host "@playwright/mcp $ver"

# 3. Browser: prefer an installed system browser, no download needed
if (-not $Browser) {
    $chromePaths = @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
    )
    if ($chromePaths | Where-Object { Test-Path $_ }) { $Browser = "chrome" } else { $Browser = "msedge" }
}
Write-Host "Browser: $Browser"

# 4. Warm the npx cache and check the server starts
Write-Host "Checking that the server starts (first run downloads the package)..."
& npx -y "@playwright/mcp@$ver" --help | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "npx @playwright/mcp@$ver --help failed." }

# 5. Persistent profile OUTSIDE the repo: it holds your Nexent login cookies, never commit it
$profile = Join-Path $env:LOCALAPPDATA "playwright-mcp-profile"
New-Item -ItemType Directory -Force -Path $profile | Out-Null

# 6. Allow the browser to talk only to Nexent (origin of the URL you gave)
$uri = [System.Uri]$NexentUrl
$origin = $uri.GetLeftPart([System.UriPartial]::Authority)

$mcpArgs = @("-y", "@playwright/mcp@$ver", "--browser", $Browser, "--user-data-dir", $profile, "--allowed-origins", $origin)
if ($Headless) { $mcpArgs += "--headless" }

$entry = [ordered]@{ command = "npx"; args = $mcpArgs; env = [ordered]@{ npm_config_cache = $npmCache } }
$snippet = [ordered]@{ mcpServers = [ordered]@{ playwright = $entry } }

$outFile = Join-Path $PSScriptRoot "claude_config_snippet.json"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($outFile, ($snippet | ConvertTo-Json -Depth 10), $utf8NoBom)
Write-Host "Config snippet written to $outFile"

# 7. Optionally merge into the Claude config file (written as UTF-8 WITHOUT BOM, which Node-based apps parse safely)
if ($ConfigPath) {
    if (Test-Path $ConfigPath) {
        Copy-Item $ConfigPath "$ConfigPath.bak" -Force
        $cfg = Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
    } else {
        $cfg = [pscustomobject]@{}
    }
    if (-not ($cfg.PSObject.Properties.Name -contains "mcpServers")) {
        $cfg | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{})
    }
    $cfg.mcpServers | Add-Member -NotePropertyName playwright -NotePropertyValue ([pscustomobject]$entry) -Force
    [System.IO.File]::WriteAllText($ConfigPath, ($cfg | ConvertTo-Json -Depth 20), $utf8NoBom)
    Write-Host "Merged into $ConfigPath (backup: $ConfigPath.bak)"
} else {
    Write-Host ""
    Write-Host "Not merged automatically. Copy the 'playwright' entry from the snippet into the mcpServers section of your Claude config (see README.md)."
}

Write-Host ""
Write-Host "Done. Fully quit and restart the Claude desktop app, then start a new session."
Write-Host "First use: a browser window opens; log in to Nexent yourself once. The login is kept in $profile."
