<#
proxy-maker: tao ban proxy (nua do phan giai, H.264 NVENC) cho tat ca video trong goc\ cua 1 du an,
ghi vao proxy\ cung du an. KHONG dong vao file goc. Chay lai thi bo qua file da co proxy.
Cho toi luot GPU qua gpu-queue (khong chay chung ComfyUI/ffmpeg khac/Resolve render).

  .\proxy-maker.ps1 -Project "D:\Quang\2026\thang 10\14.10.2026 - Ten du an"
  .\proxy-maker.ps1 -Project "..." -NoNotify     # khong gui thong bao (de test)
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Project,

    [switch]$NoNotify
)

$ErrorActionPreference = 'Stop'

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptRoot 'ingest.functions.ps1')
. (Join-Path $scriptRoot 'gpu-queue.functions.ps1')

$Config = Get-JsonFile -Path (Join-Path $scriptRoot 'ingest.config.json')
$Secrets = Get-JsonFile -Path (Join-Path $scriptRoot 'ingest.secrets.json')

$ffmpeg = (Get-Command ffmpeg -ErrorAction Stop).Source
$ffprobe = Join-Path (Split-Path $ffmpeg) 'ffprobe.exe'

# Resolve chi link proxy khi timecode khop ca kieu drop-frame (;) / non-drop (:).
# ffprobe doc timecode Sony (track rtmd) luon ra dau ':', nen doc bit drop-frame (0x40 o byte khung, chuan SMPTE)
# trong goi rtmd dau tien. Tra ve $null neu ban goc khong co timecode.
function Get-SourceTimecode {
    param([string]$Path)

    $tc = & $ffprobe -v error -show_entries stream_tags=timecode:format_tags=timecode -of default=nw=1:nk=1 $Path |
        Where-Object { $_ } | Select-Object -First 1
    if (-not $tc) { return $null }
    $tc = $tc.Trim()

    $isRtmd = (& $ffprobe -v error -select_streams d -show_entries stream=codec_tag_string -of csv=p=0 $Path) -contains 'rtmd'
    if ($isRtmd -and $tc -match '^(\d\d):(\d\d):(\d\d):(\d\d)$') {
        $tmp = [System.IO.Path]::GetTempFileName()
        try {
            & $ffmpeg -hide_banner -loglevel error -y -i $Path -map 0:d:0 -c copy -frames:d 1 -f data $tmp
            $data = [System.IO.File]::ReadAllBytes($tmp)
            $bcd = { param([int]$v) [byte]((([int][math]::Floor($v / 10)) -shl 4) -bor ($v % 10)) }
            $h = [int]$Matches[1]; $m = [int]$Matches[2]; $s = [int]$Matches[3]; $f = [int]$Matches[4]
            $tail = @((& $bcd $s), (& $bcd $m), (& $bcd $h))
            $dfFrame = [byte]((& $bcd $f) -bor 0x40)
            for ($i = 0; $i -le $data.Length - 4; $i++) {
                if ($data[$i] -eq $dfFrame -and $data[$i + 1] -eq $tail[0] -and $data[$i + 2] -eq $tail[1] -and $data[$i + 3] -eq $tail[2]) {
                    $tc = '{0}:{1}:{2};{3}' -f $Matches[1], $Matches[2], $Matches[3], $Matches[4]
                    break
                }
            }
        }
        finally { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
    }
    return $tc
}

$srcFolder = Join-Path $Project $Config.subfolders.video
$proxyFolder = Join-Path $Project 'proxy'
$projectName = Split-Path $Project -Leaf

if (-not (Test-Path -LiteralPath $srcFolder)) {
    throw "Khong thay thu muc video goc: $srcFolder"
}

$videoExt = $Config.videoExtensions
$files = @(Get-ChildItem -LiteralPath $srcFolder -File | Where-Object { $videoExt -contains $_.Extension.ToLowerInvariant() })
New-Item -ItemType Directory -Path $proxyFolder -Force | Out-Null

$made = 0; $skipped = 0
$failed = New-Object System.Collections.Generic.List[string]

if ($files.Count -gt 0) {
    # Proxy NVENC thuc su chi dung ~250 MiB VRAM (do 15/10); 600 MiB de van chay duoc khi Gemma + Resolve dang mo (con trong ~800 MiB)
    $turn = Wait-GpuTurn -Name "proxy $projectName" -NeedVramMB 600
    try {
        foreach ($file in $files) {
            $out = Join-Path $proxyFolder ($file.BaseName + '.mp4')
            if (Test-Path -LiteralPath $out) { $skipped++; continue }

            # Ghi ra .part roi doi ten khi xong, de mat dien giua chung khong de lai file proxy do dang.
            $part = "$out.part"
            Write-Host "Dang tao proxy: $($file.Name)"
            $tc = Get-SourceTimecode $file.FullName
            $tcArgs = @()
            if ($tc) { $tcArgs = @('-timecode', $tc) }
            # scale nua + ep 8-bit 4:2:0 (NVENC H.264 khong nhan 10-bit/4:2:2 cua camera). g=12 de keo timeline muot.
            & $ffmpeg -hide_banner -loglevel error -y -i $file.FullName `
                -map 0:v:0 -map '0:a?' `
                -vf 'scale=trunc(iw/4)*2:trunc(ih/4)*2,format=yuv420p' `
                -c:v h264_nvenc -preset p5 -rc vbr -cq 26 -g 12 `
                -c:a aac -b:a 160k -map_metadata 0 @tcArgs -f mp4 $part

            if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $part)) {
                Move-Item -LiteralPath $part -Destination $out
                $made++
            }
            else {
                Remove-Item -LiteralPath $part -Force -ErrorAction SilentlyContinue
                $failed.Add($file.Name)
            }
        }
    }
    finally { Release-GpuTurn $turn }
}

$msg = "$made proxy moi, $skipped da co san, $($failed.Count) loi."
if ($failed.Count -gt 0) { $msg += " File loi: $($failed -join ', ')" }
Write-Host "=== Proxy xong: $projectName - $msg"

if (-not $NoNotify) {
    Send-Notification -Title "Proxy xong: $projectName" -Message $msg -Secrets $Secrets
}

if ($failed.Count -gt 0) { exit 1 }
