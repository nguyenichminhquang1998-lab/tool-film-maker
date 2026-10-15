param([string]$Lib, [switch]$NoQueue, [int]$Seconds = 300, [string]$Log)
function Ts { [math]::Round((Get-Date).ToUniversalTime().Subtract([datetime]'1970-01-01').TotalSeconds, 2) }
"TS $(Ts) NVENC_REQUEST"
if (-not $NoQueue) {
    $ErrorActionPreference = 'Stop'   # neu khong nap duoc hang doi thi DUNG, khong chay tiep am tham
    . $Lib
    $turn = Wait-GpuTurn -Name 'nvenc-proxy' -NeedVramMB 3000 -PollSeconds 2 -IdleSamples 2 -MaxWaitMinutes 4
    $ErrorActionPreference = 'Continue'
}
"TS $(Ts) NVENC_START"
try {
    $ff = (Get-Command ffmpeg).Source
    $outTmp = "$Log.out"
    $argList = "-hide_banner -loglevel error -stats -f lavfi -i testsrc2=size=1920x1080:rate=30 -t $Seconds -c:v h264_nvenc -preset p5 -f null -"
    $p = Start-Process -FilePath $ff -ArgumentList $argList -NoNewWindow -PassThru -RedirectStandardError $Log -RedirectStandardOutput $outTmp
    if (-not $p.WaitForExit(200000)) { $p.Kill(); "NVENC_RESULT TIMEOUT" } else {
        $txt = (Get-Content $Log -Raw -ErrorAction SilentlyContinue)
        $m = [regex]::Matches([string]$txt, 'frame=\s*(\d+)\s+fps=\s*([\d.]+)')
        if ($m.Count) { $l = $m[$m.Count - 1]; "NVENC_RESULT frames=$($l.Groups[1].Value) fps=$($l.Groups[2].Value)" } else { "NVENC_RESULT khong-doc-duoc-fps" }
    }
} finally { if ($turn) { Release-GpuTurn $turn }; "TS $(Ts) NVENC_END" }
