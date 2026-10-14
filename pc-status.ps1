<#
pc-status: doc nhanh tinh trang may (GPU/VRAM, o dia, job nang dang chay).
CHI DOC, khong thay doi gi tren may.

  .\pc-status.ps1          # in ra de doc
  .\pc-status.ps1 -Json    # in JSON (de MCP/bot Telegram goi)
#>

param([switch]$Json)

$ErrorActionPreference = 'Stop'

# --- GPU ---
$gpu = $null
$smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($smi) {
    $row = & $smi.Source --query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu,utilization.encoder --format=csv,noheader,nounits
    $p = ($row | Select-Object -First 1) -split ',\s*'
    $gpu = [PSCustomObject]@{
        Name           = $p[0]
        VramUsedMB     = [int]$p[1]
        VramTotalMB    = [int]$p[2]
        UtilPercent    = [int]$p[3]
        TempC          = [int]$p[4]
        EncoderPercent = [int]$p[5]
    }
}

# --- O dia cung (khong tinh the nho/USB) ---
$disks = Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object {
    [PSCustomObject]@{
        Drive   = $_.DeviceID
        FreeGB  = [math]::Round($_.FreeSpace / 1GB, 1)
        TotalGB = [math]::Round($_.Size / 1GB)
    }
}

# --- Job nang dang chay ---
$jobs = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match '^(ffmpeg|ollama)' -or $_.Name -eq 'Resolve.exe' -or
    ($_.Name -match '^python' -and $_.CommandLine -match 'ComfyUI')
} | ForEach-Object {
    [PSCustomObject]@{ Name = $_.Name; ProcessId = $_.ProcessId }
}

# --- Canh bao ---
$warnings = New-Object System.Collections.Generic.List[string]
$c = $disks | Where-Object Drive -eq 'C:'
if ($c -and $c.FreeGB -lt 20) { $warnings.Add("O C: con $($c.FreeGB)GB, duoi 20GB.") }

$status = [PSCustomObject]@{
    Time     = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    Gpu      = $gpu
    Disks    = @($disks)
    Jobs     = @($jobs)
    Warnings = @($warnings)
}

if ($Json) {
    $status | ConvertTo-Json -Depth 4
    return
}

Write-Host "=== Tinh trang may luc $($status.Time) ==="
if ($gpu) {
    Write-Host ("GPU: {0} | VRAM {1}/{2} MB | tai {3}% | {4} do C" -f $gpu.Name, $gpu.VramUsedMB, $gpu.VramTotalMB, $gpu.UtilPercent, $gpu.TempC)
}
else {
    Write-Host 'GPU: khong thay nvidia-smi.'
}
foreach ($d in $disks) { Write-Host ("O {0} con {1} GB / {2} GB" -f $d.Drive, $d.FreeGB, $d.TotalGB) }
if ($jobs) { foreach ($j in $jobs) { Write-Host ("Dang chay: {0} (PID {1})" -f $j.Name, $j.ProcessId) } }
else { Write-Host 'Khong co job nang nao dang chay (ffmpeg / ComfyUI / Resolve / ollama).' }
foreach ($w in $warnings) { Write-Host "CANH BAO: $w" -ForegroundColor Yellow }
