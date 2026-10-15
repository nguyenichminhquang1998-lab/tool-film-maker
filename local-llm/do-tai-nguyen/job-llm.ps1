param([string]$Lib, [switch]$NoQueue, [string]$Py, [string]$Script, [string]$KeepAlive = '0', [string]$Tmp)
function Ts { [math]::Round((Get-Date).ToUniversalTime().Subtract([datetime]'1970-01-01').TotalSeconds, 2) }
"TS $(Ts) LLM_REQUEST"
if (-not $NoQueue) {
    $ErrorActionPreference = 'Stop'   # neu khong nap duoc hang doi thi DUNG, khong chay tiep am tham
    . $Lib
    $turn = Wait-GpuTurn -Name 'llm-zalo' -NeedVramMB 9500 -PollSeconds 2 -IdleSamples 2 -MaxWaitMinutes 4
    $ErrorActionPreference = 'Continue'
}
"TS $(Ts) LLM_START"
try {
    $p = Start-Process -FilePath $Py -ArgumentList "-I `"$Script`" $KeepAlive" -NoNewWindow -PassThru -RedirectStandardOutput "$Tmp.out" -RedirectStandardError "$Tmp.err"
    if (-not $p.WaitForExit(200000)) { $p.Kill(); "ZALO_TIMEOUT" } else { Get-Content "$Tmp.out" -ErrorAction SilentlyContinue | Where-Object { $_ -match 'ZALO_RESULT' } }
} finally { if ($turn) { Release-GpuTurn $turn }; "TS $(Ts) LLM_END" }
