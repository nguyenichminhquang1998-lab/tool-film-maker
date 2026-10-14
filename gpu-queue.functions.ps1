<#
Hang doi GPU: moi luc chi 1 job nang chay, va job chi chay khi GPU thuc su ranh.
Job den sau thi CHO (khong bi tu choi), de VRAM khong bi tran.

Dung:
  . .\gpu-queue.functions.ps1
  $turn = Wait-GpuTurn -Name 'proxy MV To Vuong'
  try { ... viec nang ... } finally { Release-GpuTurn $turn }
#>

function Get-GpuBusyReason {
    param([int]$NeedVramMB)

    $statusScript = Join-Path $PSScriptRoot 'pc-status.ps1'
    $s = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $statusScript -Json | ConvertFrom-Json
    if (-not $s.Gpu) { return 'khong doc duoc GPU (nvidia-smi)' }

    # ffmpeg / ComfyUI (python) chay ngoai hang doi. Resolve mo san khong tinh, Resolve render thi bat qua tai GPU/encoder.
    $other = @($s.Jobs | Where-Object { $_.Name -match '^(ffmpeg|python)' })
    if ($other.Count -gt 0) { return "dang chay $($other[0].Name)" }

    if ($s.Gpu.UtilPercent -ge 30 -or $s.Gpu.EncoderPercent -ge 30) {
        return "GPU dang ban (tai $($s.Gpu.UtilPercent)%, encoder $($s.Gpu.EncoderPercent)%)"
    }

    $free = $s.Gpu.VramTotalMB - $s.Gpu.VramUsedMB
    if ($free -lt $NeedVramMB) { return "VRAM trong chi con $free MB, can $NeedVramMB MB" }

    return $null
}

function Wait-GpuTurn {
    param(
        [string]$Name,
        [int]$NeedVramMB = 3000,
        [int]$PollSeconds = 10,
        [int]$IdleSamples = 3,
        [int]$MaxWaitMinutes = 600
    )

    $mutex = New-Object System.Threading.Mutex($false, 'Global\JavisGpuQueue')
    $held = $false
    $deadline = (Get-Date).AddMinutes($MaxWaitMinutes)
    $lastLog = [datetime]::MinValue

    try {
        # 1) cho toi luot (chi 1 job giu chia khoa)
        while (-not $held) {
            try { $held = $mutex.WaitOne(1000) }
            catch [System.Threading.AbandonedMutexException] { $held = $true }
            if ($held) { break }
            if ((Get-Date) -gt $deadline) { throw "Cho qua $MaxWaitMinutes phut van chua toi luot GPU: $Name" }
            if (((Get-Date) - $lastLog).TotalSeconds -ge 60) {
                Write-Host "[gpu-queue] $($Name): dang xep hang, job khac dang giu GPU..."
                $lastLog = Get-Date
            }
        }

        # 2) cho GPU ranh lien tuc $IdleSamples lan do
        $idle = 0
        while ($idle -lt $IdleSamples) {
            $reason = Get-GpuBusyReason -NeedVramMB $NeedVramMB
            if ($reason) {
                $idle = 0
                if ((Get-Date) -gt $deadline) { throw "Cho qua $MaxWaitMinutes phut van chua ranh GPU ($reason): $Name" }
                if (((Get-Date) - $lastLog).TotalSeconds -ge 60) {
                    Write-Host "[gpu-queue] $($Name): cho GPU - $reason"
                    $lastLog = Get-Date
                }
                Start-Sleep -Seconds $PollSeconds
            }
            else {
                $idle++
                if ($idle -lt $IdleSamples) { Start-Sleep -Seconds $PollSeconds }
            }
        }
    }
    catch {
        if ($held) { $mutex.ReleaseMutex() }
        $mutex.Dispose()
        throw
    }

    Write-Host "[gpu-queue] $($Name): GPU ranh, bat dau chay."
    return $mutex
}

function Release-GpuTurn {
    param($Mutex)
    if ($Mutex) {
        $Mutex.ReleaseMutex()
        $Mutex.Dispose()
    }
}
