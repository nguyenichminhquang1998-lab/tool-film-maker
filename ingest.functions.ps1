<#
Thu vien function dung chung cho pipeline do the: CLI (ingest.ps1/ingest.bat)
va GUI (ingest-gui.ps1) deu dot-source file nay, dam bao chi 1 noi giu logic.
#>

# ============================================================
# Helpers
# ============================================================

function Get-JsonFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    if (-not $raw) { return $null }
    return $raw | ConvertFrom-Json
}

function Send-WindowsToast {
    param([string]$Title, [string]$Message)
    try {
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -AssemblyName System.Drawing
        $notifyIcon = New-Object System.Windows.Forms.NotifyIcon
        $notifyIcon.Icon = [System.Drawing.SystemIcons]::Information
        $notifyIcon.Visible = $true
        $notifyIcon.BalloonTipTitle = $Title
        $notifyIcon.BalloonTipText = $Message
        $notifyIcon.ShowBalloonTip(8000)
        Start-Sleep -Seconds 5
        $notifyIcon.Dispose()
    }
    catch {
        Write-Warning "Khong gui duoc thong bao Windows: $($_.Exception.Message)"
    }
}

function Send-TelegramMessage {
    param([string]$Token, [string]$ChatId, [string]$Text)
    if (-not $Token -or -not $ChatId) { return }
    try {
        $uri = "https://api.telegram.org/bot$($Token)/sendMessage"
        $payload = @{ chat_id = $ChatId; text = $Text } | ConvertTo-Json -Compress
        $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
        Invoke-RestMethod -Uri $uri -Method Post -ContentType 'application/json; charset=utf-8' -Body $bodyBytes | Out-Null
    }
    catch {
        $detail = $_.Exception.Message
        if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
            $detail = $_.ErrorDetails.Message
        }
        elseif ($_.Exception.Response) {
            try {
                $stream = $_.Exception.Response.GetResponseStream()
                $reader = New-Object System.IO.StreamReader($stream)
                $detail = $reader.ReadToEnd()
            }
            catch { }
        }
        Write-Warning "Khong gui duoc Telegram: $detail"
    }
}

function Send-Notification {
    param([string]$Title, [string]$Message, $Secrets)
    Send-WindowsToast -Title $Title -Message $Message
    if ($Secrets) {
        Send-TelegramMessage -Token $Secrets.telegramBotToken -ChatId $Secrets.telegramChatId -Text "$($Title)`n$($Message)"
    }
}

# ============================================================
# Buoc 1: tao cau truc thu muc du an
# ============================================================

function New-ProjectFolder {
    param($Config, [datetime]$ShootDate, [string]$ProjectName)

    $year = $ShootDate.Year.ToString()
    $monthFolder = "$($Config.monthFolderPrefix)$($ShootDate.Month)"
    $dateStr = $ShootDate.ToString('d.M.yyyy')
    $projectFolderName = "$dateStr - $ProjectName"

    $projectFolder = Join-Path (Join-Path (Join-Path $Config.basePath $year) $monthFolder) $projectFolderName

    $photoFolder = Join-Path $projectFolder $Config.subfolders.photo
    $videoFolder = Join-Path $projectFolder $Config.subfolders.video
    $musicFolder = Join-Path $projectFolder $Config.subfolders.music

    New-Item -ItemType Directory -Path $photoFolder -Force | Out-Null
    New-Item -ItemType Directory -Path $videoFolder -Force | Out-Null
    New-Item -ItemType Directory -Path $musicFolder -Force | Out-Null

    Write-Host "Da tao/kiem tra thu muc du an: $projectFolder"

    return [PSCustomObject]@{
        ProjectFolder     = $projectFolder
        PhotoFolder       = $photoFolder
        VideoFolder       = $videoFolder
        MusicFolder       = $musicFolder
        Year              = $year
        MonthFolder       = $monthFolder
        ProjectFolderName = $projectFolderName
    }
}

# ============================================================
# Buoc 2: copy tu the + phan loai theo duoi file
# ============================================================

function Copy-CardContents {
    param([string]$CardDrive, $Paths, $Config, [string]$LogFile)

    if (-not (Test-Path -LiteralPath $CardDrive)) {
        throw "Khong tim thay o the nho: $CardDrive"
    }

    Write-Host "Dang quet the nho $CardDrive ..."
    $allFiles = Get-ChildItem -LiteralPath $CardDrive -Recurse -File -ErrorAction SilentlyContinue

    if (-not $allFiles -or $allFiles.Count -eq 0) {
        throw "The nho $CardDrive khong co file nao."
    }

    $photoExt = $Config.photoExtensions
    $videoExt = $Config.videoExtensions
    $fallback = $Config.unknownExtensionFallback

    $summary = [PSCustomObject]@{
        PhotoCount       = 0
        VideoCount       = 0
        UnknownCount     = 0
        SourceFileCount  = $allFiles.Count
        SourceTotalBytes = 0
        CopiedFileCount  = 0
        CopiedTotalBytes = 0
        SkippedDuplicate = 0
        RenamedCollision = 0
        Errors           = New-Object System.Collections.Generic.List[string]
    }

    foreach ($file in $allFiles) {
        $summary.SourceTotalBytes += $file.Length
        $ext = $file.Extension.ToLowerInvariant()

        if ($photoExt -contains $ext) {
            $destFolder = $Paths.PhotoFolder
            $summary.PhotoCount++
        }
        elseif ($videoExt -contains $ext) {
            $destFolder = $Paths.VideoFolder
            $summary.VideoCount++
        }
        else {
            $summary.UnknownCount++
            if ($fallback -eq 'photo') {
                $destFolder = $Paths.PhotoFolder
                $summary.PhotoCount++
            }
            else {
                $destFolder = $Paths.VideoFolder
                $summary.VideoCount++
            }
            Add-Content -LiteralPath $LogFile -Value "CANH BAO: duoi file la '$ext' -> $($file.FullName) da copy vao $destFolder theo fallback"
        }

        $destPath = Join-Path $destFolder $file.Name

        if (Test-Path -LiteralPath $destPath) {
            $existing = Get-Item -LiteralPath $destPath
            if ($existing.Length -eq $file.Length) {
                $summary.SkippedDuplicate++
                Add-Content -LiteralPath $LogFile -Value "BO QUA (da co, cung size): $($file.FullName)"
                continue
            }
            else {
                $baseName = [System.IO.Path]::GetFileNameWithoutExtension($file.Name)
                $extName = $file.Extension
                $n = 1
                do {
                    $destPath = Join-Path $destFolder "$($baseName)_dup$($n)$($extName)"
                    $n++
                } while (Test-Path -LiteralPath $destPath)
                $summary.RenamedCollision++
                Add-Content -LiteralPath $LogFile -Value "TRUNG TEN KHAC SIZE: $($file.FullName) -> doi ten thanh $destPath"
            }
        }

        $copied = $false
        $attempt = 0
        $maxAttempts = 5
        while (-not $copied -and $attempt -lt $maxAttempts) {
            $attempt++
            try {
                Copy-Item -LiteralPath $file.FullName -Destination $destPath -Force
                $copied = $true
            }
            catch {
                if ($attempt -ge $maxAttempts) {
                    $msg = "LOI copy sau $maxAttempts lan thu: $($file.FullName) -> $($_.Exception.Message)"
                    $summary.Errors.Add($msg)
                    Add-Content -LiteralPath $LogFile -Value $msg
                }
                else {
                    Start-Sleep -Seconds ([Math]::Pow(2, $attempt))
                }
            }
        }

        if ($copied) {
            $summary.CopiedFileCount++
            $summary.CopiedTotalBytes += $file.Length
            Add-Content -LiteralPath $LogFile -Value "OK: $($file.FullName) -> $destPath"
        }
    }

    if ($summary.Errors.Count -gt 0) {
        throw "Copy that bai $($summary.Errors.Count) file. Xem log: $LogFile"
    }

    return $summary
}

# ============================================================
# Buoc 3: xac minh copy day du truoc khi cho phep format the
# ============================================================

function Test-CopyIntegrity {
    param($Summary, [string]$LogFile)

    $accountedFor = $Summary.CopiedFileCount + $Summary.SkippedDuplicate
    if ($accountedFor -ne $Summary.SourceFileCount) {
        throw "KHONG KHOP so luong file: nguon $($Summary.SourceFileCount), da xu ly $accountedFor. KHONG an toan de xoa/format the. Xem log: $LogFile"
    }

    Write-Host "Xac minh OK: $($Summary.SourceFileCount) file nguon, $($Summary.CopiedFileCount) da copy moi, $($Summary.SkippedDuplicate) da co san (bo qua), $($Summary.RenamedCollision) trung ten da doi ten."
    Write-Host "-> AN TOAN de format the nho (du lieu da duoc xac minh day du tren may)."
}

# ============================================================
# Buoc 4: nen goc/ (raw footage) - che do store, khong nen that
# ============================================================

function Compress-RawFootage {
    param($Paths, $Config, [string]$ProjectName, [string]$LogFile)

    $sevenZipCmd = Get-Command '7z.exe' -ErrorAction SilentlyContinue
    if ($sevenZipCmd) {
        $sevenZipPath = $sevenZipCmd.Source
    }
    else {
        $candidatePaths = @(
            "$env:ProgramFiles\7-Zip\7z.exe",
            "${env:ProgramFiles(x86)}\7-Zip\7z.exe"
        )
        $found = $candidatePaths | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        if (-not $found) {
            throw "Khong tim thay 7z.exe. Cai 7-Zip (https://www.7-zip.org/) roi thu lai, hoac them 7z.exe vao PATH."
        }
        $sevenZipPath = $found
    }

    $archiveName = "$($ProjectName)_goc.7z"
    $archivePath = Join-Path $Paths.ProjectFolder $archiveName

    Write-Host "Dang dong goi goc/ (che do store, khong nen that) -> $archivePath ..."
    $sourcePattern = Join-Path $Paths.VideoFolder '*'
    $sevenZipArgs = @('a', '-t7z', '-mx=0', $archivePath, $sourcePattern)

    $stdOutLog = "$($LogFile).7z.out.log"
    $stdErrLog = "$($LogFile).7z.err.log"
    & $sevenZipPath @sevenZipArgs 1> $stdOutLog 2> $stdErrLog
    $sevenZipExitCode = $LASTEXITCODE

    if ($sevenZipExitCode -ne 0) {
        throw "7-Zip loi (exit code $sevenZipExitCode). Xem $stdErrLog"
    }

    $archiveItem = Get-Item -LiteralPath $archivePath
    Write-Host "Dong goi xong: $archivePath ($([Math]::Round($archiveItem.Length / 1GB, 2)) GB)"
    return $archiveItem
}

# ============================================================
# Buoc 5: upload len Google Drive / OneDrive qua rclone
# ============================================================

function Get-RcloneFreeSpaceBytes {
    param([string]$RemoteName)
    try {
        $json = & rclone about "$($RemoteName):" --json 2>$null
        if (-not $json) { return $null }
        $obj = $json | ConvertFrom-Json
        if ($obj.free) { return [int64]$obj.free }
        return $null
    }
    catch {
        return $null
    }
}

function Publish-ToCloud {
    param([string]$ArchivePath, [string]$Dest, $Config, [string]$LogFile, $Paths)

    if (-not (Get-Command 'rclone' -ErrorAction SilentlyContinue)) {
        throw "Khong tim thay rclone. Cai tai https://rclone.org/downloads/ va chay 'rclone config' de thiet lap remote truoc."
    }

    $targets = @()
    if ($Dest -eq 'drive' -or $Dest -eq 'both') { $targets += $Config.rcloneRemotes.drive }
    if ($Dest -eq 'onedrive' -or $Dest -eq 'both') { $targets += $Config.rcloneRemotes.onedrive }

    $archiveItem = Get-Item -LiteralPath $ArchivePath
    $remoteRelativePath = "$($Config.cloudRootFolder)/$($Paths.Year)/$($Paths.MonthFolder)/$($Paths.ProjectFolderName)"
    $results = @()

    foreach ($remote in $targets) {
        $freeBytes = Get-RcloneFreeSpaceBytes -RemoteName $remote
        if ($null -ne $freeBytes) {
            if ($freeBytes -lt $archiveItem.Length) {
                throw "Remote '$remote' khong du dung luong trong ($([Math]::Round($freeBytes/1GB,2)) GB) cho file $([Math]::Round($archiveItem.Length/1GB,2)) GB. Dung lai de tranh upload do dang."
            }
            $warnThresholdBytes = [int64]$Config.cloudFreeSpaceWarningGB * 1GB
            if (($freeBytes - $archiveItem.Length) -lt $warnThresholdBytes) {
                Write-Warning "Remote '$remote' se con duoi $($Config.cloudFreeSpaceWarningGB) GB trong sau khi upload file nay."
            }
        }
        else {
            Write-Warning "Khong kiem tra duoc dung luong trong cua remote '$remote' - tiep tuc upload."
        }

        $remoteTarget = "$($remote):$remoteRelativePath"
        Write-Host "Dang upload len $remoteTarget ..."
        $rcloneLog = "$($LogFile).rclone.$($remote).log"
        & rclone copy $ArchivePath $remoteTarget --retries 5 --low-level-retries 10 --log-file="$rcloneLog" --log-level INFO | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "rclone upload len '$remote' that bai (exit code $LASTEXITCODE). Xem $rcloneLog"
        }
        Write-Host "Upload len $remote xong."
        $results += $remoteTarget
    }

    return $results
}
