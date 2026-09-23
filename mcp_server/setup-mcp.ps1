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
    # Claude Desktop luu ca preferences cua no vao chinh file nay - neu app dang chay,
    # no se ghi de lai ban trong bo nho va lam mat dong vua them.
    # Chi nham app Claude Desktop (chay duoi quyen user, doc duoc Path). Tien trinh
    # 'claude' khac (Claude Code / Cowork nen, co the chay quyen cao) khong dung vao
    # file cau hinh nay nen bo qua, khong co tat.
    function Get-ClaudeDesktopProcess {
        Get-Process -Name 'Claude' -ErrorAction SilentlyContinue | Where-Object {
            $_.Path -and (
                $_.Path -like '*\WindowsApps\Claude_*' -or
                $_.Path -like '*\AnthropicClaude\*'
            )
        }
    }

    $running = @(Get-ClaudeDesktopProcess)
    if ($running.Count -gt 0) {
        Write-Host "    Claude Desktop dang chay - phai tat han truoc khi ghi, neu khong app se ghi de mat cau hinh." -ForegroundColor Yellow
        Read-Host "    Luu lai viec dang lam trong Claude (neu co), roi nhan Enter de script tu tat Claude"
        foreach ($p in $running) {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 3
        if (@(Get-ClaudeDesktopProcess).Count -gt 0) {
            throw "Khong tat duoc Claude Desktop. Tat tay: Ctrl+Shift+Esc -> tab Details -> End task moi dong Claude.exe, roi chay lai file nay."
        }
        Write-Ok "Da tat Claude Desktop"
    }
    $configPath = Set-McpConfig -ConfigDir $configDir -PythonExe $python -ServerPy $serverPy
    Write-Ok "Da ghi: $configPath"

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host " XONG. Viec cuoi cung ban tu lam:" -ForegroundColor Green
    Write-Host "  1. Mo lai Claude Desktop tu Start Menu" -ForegroundColor Green
    Write-Host "  2. Settings -> Developer: phai thay tool-film-maker" -ForegroundColor Green
    Write-Host "  3. Go thu: dung tool-film-maker liet ke the nho dang cam" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
}
catch {
    Write-Fail $_.Exception.Message
    exit 1
}
