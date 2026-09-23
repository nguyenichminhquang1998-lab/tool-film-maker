<#
Cai dat tu dong MCP server cho Claude Desktop:
  1. Tim file cau hinh Claude Desktop (ban cai thuong VA ban Microsoft Store)
  2. Tim Python that (bo qua ban gia cua Microsoft Store), cai qua winget neu thieu
  3. pip install thu vien MCP
  4. Ghi cau hinh tool-film-maker vao claude_desktop_config.json (sao luu file cu truoc)
#>

param(
    [string]$ConfigDirOverride
)

$ErrorActionPreference = 'Stop'

$serverDir = $PSScriptRoot
$serverPy = Join-Path $serverDir 'server.py'
$requirements = Join-Path $serverDir 'requirements.txt'

function Write-Step { param([string]$Text) Write-Host ""; Write-Host "==> $Text" -ForegroundColor Cyan }
function Write-Ok { param([string]$Text) Write-Host "    OK: $Text" -ForegroundColor Green }
function Write-Fail { param([string]$Text) Write-Host "    LOI: $Text" -ForegroundColor Red }

# ------------------------------------------------------------
# 1. Tim thu muc cau hinh Claude Desktop
# ------------------------------------------------------------
function Find-ClaudeConfigDir {
    if ($ConfigDirOverride) { return $ConfigDirOverride }

    $standard = Join-Path $env:APPDATA 'Claude'
    if (Test-Path -LiteralPath $standard) { return $standard }

    $packagesRoot = Join-Path $env:LOCALAPPDATA 'Packages'
    if (Test-Path -LiteralPath $packagesRoot) {
        $storeDir = Get-ChildItem -LiteralPath $packagesRoot -Directory -Filter 'Claude_*' -ErrorAction SilentlyContinue |
            ForEach-Object { Join-Path $_.FullName 'LocalCache\Roaming\Claude' } |
            Where-Object { Test-Path -LiteralPath $_ } |
            Select-Object -First 1
        if ($storeDir) { return $storeDir }
    }
    return $null
}

# ------------------------------------------------------------
# 2. Tim Python that (khong phai lenh gia mo Microsoft Store)
# ------------------------------------------------------------
function Find-RealPython {
    foreach ($cmd in @('python', 'py')) {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue
        if (-not $found) { continue }
        if ($found.Source -like '*\WindowsApps\*') { continue }
        try {
            $exe = & $found.Source -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $exe -and (Test-Path -LiteralPath $exe.Trim())) {
                return $exe.Trim()
            }
        }
        catch { }
    }
    return $null
}

function Update-SessionPath {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machine;$user"
}

# ------------------------------------------------------------
# 3. Ghi cau hinh vao claude_desktop_config.json (giu nguyen cau hinh khac)
# ------------------------------------------------------------
function Set-McpConfig {
    param([string]$ConfigDir, [string]$PythonExe, [string]$ServerPy)

    $configPath = Join-Path $ConfigDir 'claude_desktop_config.json'
    $config = $null

    if (Test-Path -LiteralPath $configPath) {
        $backup = "$configPath.bak-$(Get-Date -Format 'yyyyMMdd_HHmmss')"
        Copy-Item -LiteralPath $configPath -Destination $backup
        Write-Ok "Da sao luu file cau hinh cu: $backup"

        $raw = [System.IO.File]::ReadAllText($configPath)
        if ($raw.Trim()) {
            try {
                $config = $raw | ConvertFrom-Json
            }
            catch {
                throw "File cau hinh hien tai bi loi cu phap JSON, khong dam sua de tranh mat du lieu: $configPath"
            }
        }
    }

    if (-not $config) { $config = [PSCustomObject]@{} }
    if (-not ($config.PSObject.Properties.Name -contains 'mcpServers')) {
        $config | Add-Member -NotePropertyName 'mcpServers' -NotePropertyValue ([PSCustomObject]@{})
    }

    $entry = [PSCustomObject]@{
        command = $PythonExe
        args    = [object[]]@($ServerPy)
    }
    $config.mcpServers | Add-Member -NotePropertyName 'tool-film-maker' -NotePropertyValue $entry -Force

    $json = $config | ConvertTo-Json -Depth 20
    [System.IO.File]::WriteAllText($configPath, $json, (New-Object System.Text.UTF8Encoding($false)))
    return $configPath
}

# ============================================================
# Main
# ============================================================

try {
    Write-Step "Buoc 1/4: Tim thu muc cau hinh Claude Desktop"
    $configDir = Find-ClaudeConfigDir
    if (-not $configDir) {
        Write-Fail "Khong tim thay Claude Desktop tren may nay."
        Write-Host "    -> Cai Claude Desktop tai https://claude.ai/download, MO APP LEN 1 LAN (dang nhap), roi chay lai file nay."
        exit 1
    }
    Write-Ok $configDir

    Write-Step "Buoc 2/4: Kiem tra Python"
    $python = Find-RealPython
    if (-not $python) {
        Write-Host "    Chua co Python - dang cai qua winget (mat 1-3 phut)..."
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
            Write-Fail "May khong co winget de tu cai. Cai tay Python tai https://www.python.org/downloads/ (tick 'Add python.exe to PATH') roi chay lai file nay."
            exit 1
        }
        & winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
        Update-SessionPath
        $python = Find-RealPython
        if (-not $python) {
            Write-Fail "Da cai nhung chua nhan duoc Python. Dong cua so nay, mo lai file cai dat 1 lan nua."
            exit 1
        }
    }
    Write-Ok $python

    Write-Step "Buoc 3/4: Cai thu vien MCP (pip install)"
    & $python -m pip install --upgrade pip --quiet
    & $python -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) { throw "pip install that bai (exit code $LASTEXITCODE)." }
    & $python -c "from mcp.server.mcpserver import MCPServer"
    if ($LASTEXITCODE -ne 0) { throw "Cai xong nhung khong import duoc thu vien mcp." }
    Write-Ok "Thu vien MCP da san sang"

    Write-Step "Buoc 4/4: Ghi cau hinh vao Claude Desktop"
    $configPath = Set-McpConfig -ConfigDir $configDir -PythonExe $python -ServerPy $serverPy
    Write-Ok "Da ghi: $configPath"

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host " XONG. Viec cuoi cung ban tu lam:" -ForegroundColor Green
    Write-Host "  1. Tat HAN Claude Desktop: chuot phai icon Claude o khay he thong" -ForegroundColor Green
    Write-Host "     (goc duoi phai, canh dong ho) -> Quit" -ForegroundColor Green
    Write-Host "  2. Mo lai Claude Desktop" -ForegroundColor Green
    Write-Host "  3. Go thu: liet ke cac the nho dang cam vao may" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
}
catch {
    Write-Fail $_.Exception.Message
    exit 1
}
