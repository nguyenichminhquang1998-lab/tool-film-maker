<#
Do the tu dong (ban dong lenh - CLI): copy tu the nho -> tao folder du an ->
phan loai anh/video -> nen goc/ (raw footage) -> upload Google Drive/OneDrive
-> thong bao.

Cach chay don gian nhat: double-click ingest.bat (no se hoi ten du an,
o dia the, va dich cloud roi tu goi script nay).

Muon giao dien cua so that (khong go lenh) thi dung ingest-gui.ps1 thay the -
ca hai file deu dung chung logic trong ingest.functions.ps1.

Chay truc tiep vi du:
  .\ingest.ps1 -CardDrive "E:" -ProjectName "Kid dance bsixteen" -Dest both
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$CardDrive,

    [Parameter(Mandatory = $true)]
    [string]$ProjectName,

    [ValidateSet('drive', 'onedrive', 'both')]
    [string]$Dest = 'both',

    [datetime]$ShootDate = (Get-Date),

    [switch]$SkipCompress,

    [switch]$SkipUpload
)

$ErrorActionPreference = 'Stop'

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptRoot 'ingest.functions.ps1')

# ============================================================
# Main
# ============================================================

if (-not $CardDrive.EndsWith('\')) {
    $CardDrive = "$CardDrive\"
}

$configPath = Join-Path $scriptRoot 'ingest.config.json'
$secretsPath = Join-Path $scriptRoot 'ingest.secrets.json'

$Config = Get-JsonFile -Path $configPath
if (-not $Config) {
    throw "Khong tim thay ingest.config.json canh script ($configPath)."
}

$Secrets = Get-JsonFile -Path $secretsPath
if (-not $Secrets) {
    Write-Warning "Chua co ingest.secrets.json - bo qua thong bao Telegram (chi co Windows toast). Xem README de tao bot Telegram."
}

$logFolder = Join-Path $scriptRoot $Config.logFolderName
New-Item -ItemType Directory -Path $logFolder -Force | Out-Null
$safeProjectName = ($ProjectName -replace '[\\/:*?"<>|]', '_')
$LogFile = Join-Path $logFolder "$(Get-Date -Format 'yyyyMMdd_HHmmss')_$($safeProjectName).log"
New-Item -ItemType File -Path $LogFile -Force | Out-Null

try {
    Write-Host "=== Bat dau do the: $ProjectName ($CardDrive) ==="

    $Paths = New-ProjectFolder -Config $Config -ShootDate $ShootDate -ProjectName $ProjectName

    $summary = Copy-CardContents -CardDrive $CardDrive -Paths $Paths -Config $Config -LogFile $LogFile

    Test-CopyIntegrity -Summary $summary -LogFile $LogFile

    $archiveInfo = $null
    if (-not $SkipCompress) {
        $archiveInfo = Compress-RawFootage -Paths $Paths -Config $Config -ProjectName $ProjectName -LogFile $LogFile
    }

    $uploadResults = $null
    if (-not $SkipUpload -and $archiveInfo) {
        $uploadResults = Publish-ToCloud -ArchivePath $archiveInfo.FullName -Dest $Dest -Config $Config -LogFile $LogFile -Paths $Paths
    }

    $doneMsg = "$($summary.PhotoCount) anh, $($summary.VideoCount) video da do vao $($Paths.ProjectFolder)."
    if ($uploadResults) { $doneMsg += " Da upload: $($uploadResults -join ', ')" }
    Write-Host $doneMsg
    try {
        Send-Notification -Title "Do the xong: $ProjectName" -Message $doneMsg -Secrets $Secrets
    }
    catch {
        Write-Warning "Pipeline da chay xong OK nhung gui thong bao bi loi: $($_.Exception.Message)"
    }
}
catch {
    $errMsg = $_.Exception.Message
    Write-Host "LOI: $errMsg" -ForegroundColor Red
    try {
        Send-Notification -Title "LOI do the: $ProjectName" -Message $errMsg -Secrets $Secrets
    }
    catch {
        Write-Warning "Khong gui duoc thong bao loi: $($_.Exception.Message)"
    }
    exit 1
}
