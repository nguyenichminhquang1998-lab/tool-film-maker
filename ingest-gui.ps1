<#
Giao dien cua so (GUI) cho pipeline do the - khong can go lenh.
Tu dong nhan dien the nho khi cam vao, hien so file/dung luong va
uoc tinh thoi gian truoc khi bat dau.

Dung chung logic voi ingest.ps1 qua ingest.functions.ps1.

Chay: double-click IngestApp.exe (sau khi dong goi bang ps2exe, xem README)
hoac chay truc tiep: powershell.exe -File ingest-gui.ps1
#>

param()

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptRoot 'ingest.functions.ps1')

$configPath = Join-Path $scriptRoot 'ingest.config.json'
$secretsPath = Join-Path $scriptRoot 'ingest.secrets.json'

$Config = Get-JsonFile -Path $configPath
if (-not $Config) {
    [System.Windows.Forms.MessageBox]::Show("Khong tim thay ingest.config.json canh script.", "Loi", 'OK', 'Error') | Out-Null
    exit 1
}

# ============================================================
# Xay giao dien
# ============================================================

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Do the tu dong - tool-film-maker'
$form.Size = New-Object System.Drawing.Size(620, 680)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedSingle'
$form.MaximizeBox = $false
$form.BackColor = [System.Drawing.Color]::White

$lblProject = New-Object System.Windows.Forms.Label
$lblProject.Text = 'Ten du an:'
$lblProject.Location = New-Object System.Drawing.Point(20, 22)
$lblProject.AutoSize = $true
$form.Controls.Add($lblProject)

$txtProject = New-Object System.Windows.Forms.TextBox
$txtProject.Location = New-Object System.Drawing.Point(150, 18)
$txtProject.Size = New-Object System.Drawing.Size(430, 24)
$form.Controls.Add($txtProject)

$lblDrive = New-Object System.Windows.Forms.Label
$lblDrive.Text = 'The nho:'
$lblDrive.Location = New-Object System.Drawing.Point(20, 60)
$lblDrive.AutoSize = $true
$form.Controls.Add($lblDrive)

$cmbDrive = New-Object System.Windows.Forms.ComboBox
$cmbDrive.Location = New-Object System.Drawing.Point(150, 56)
$cmbDrive.Size = New-Object System.Drawing.Size(300, 24)
$cmbDrive.DropDownStyle = 'DropDownList'
$form.Controls.Add($cmbDrive)

$btnRefreshDrive = New-Object System.Windows.Forms.Button
$btnRefreshDrive.Text = 'Lam moi'
$btnRefreshDrive.Location = New-Object System.Drawing.Point(460, 55)
$btnRefreshDrive.Size = New-Object System.Drawing.Size(120, 26)
$form.Controls.Add($btnRefreshDrive)

$lblCardInfo = New-Object System.Windows.Forms.Label
$lblCardInfo.Text = 'Cam the nho vao de tu dong quet, hoac chon o dia roi bam "Quet lai".'
$lblCardInfo.Location = New-Object System.Drawing.Point(20, 96)
$lblCardInfo.Size = New-Object System.Drawing.Size(440, 20)
$lblCardInfo.ForeColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$form.Controls.Add($lblCardInfo)

$btnScanAgain = New-Object System.Windows.Forms.Button
$btnScanAgain.Text = 'Quet lai'
$btnScanAgain.Location = New-Object System.Drawing.Point(460, 93)
$btnScanAgain.Size = New-Object System.Drawing.Size(120, 24)
$form.Controls.Add($btnScanAgain)

$lblEta = New-Object System.Windows.Forms.Label
$lblEta.Text = ''
$lblEta.Location = New-Object System.Drawing.Point(20, 120)
$lblEta.Size = New-Object System.Drawing.Size(560, 20)
$lblEta.ForeColor = [System.Drawing.Color]::FromArgb(0, 90, 158)
$form.Controls.Add($lblEta)

$grpDest = New-Object System.Windows.Forms.GroupBox
$grpDest.Text = 'Upload len'
$grpDest.Location = New-Object System.Drawing.Point(20, 150)
$grpDest.Size = New-Object System.Drawing.Size(560, 50)
$form.Controls.Add($grpDest)

$radDrive = New-Object System.Windows.Forms.RadioButton
$radDrive.Text = 'Google Drive'
$radDrive.Location = New-Object System.Drawing.Point(15, 20)
$radDrive.AutoSize = $true
$grpDest.Controls.Add($radDrive)

$radOnedrive = New-Object System.Windows.Forms.RadioButton
$radOnedrive.Text = 'OneDrive'
$radOnedrive.Location = New-Object System.Drawing.Point(170, 20)
$radOnedrive.AutoSize = $true
$grpDest.Controls.Add($radOnedrive)

$radBoth = New-Object System.Windows.Forms.RadioButton
$radBoth.Text = 'Ca hai'
$radBoth.Location = New-Object System.Drawing.Point(300, 20)
$radBoth.AutoSize = $true
$radBoth.Checked = $true
$grpDest.Controls.Add($radBoth)

$chkSkipUpload = New-Object System.Windows.Forms.CheckBox
$chkSkipUpload.Text = 'Chi copy + nen, khong upload (khong co mang)'
$chkSkipUpload.Location = New-Object System.Drawing.Point(410, 22)
$chkSkipUpload.AutoSize = $true
$grpDest.Controls.Add($chkSkipUpload)

$btnStart = New-Object System.Windows.Forms.Button
$btnStart.Text = 'Bat dau do the'
$btnStart.Location = New-Object System.Drawing.Point(20, 210)
$btnStart.Size = New-Object System.Drawing.Size(560, 42)
$btnStart.Font = New-Object System.Drawing.Font($btnStart.Font.FontFamily, 12, [System.Drawing.FontStyle]::Bold)
$btnStart.BackColor = [System.Drawing.Color]::FromArgb(46, 125, 50)
$btnStart.ForeColor = [System.Drawing.Color]::White
$form.Controls.Add($btnStart)

$progressBar = New-Object System.Windows.Forms.ProgressBar
$progressBar.Location = New-Object System.Drawing.Point(20, 262)
$progressBar.Size = New-Object System.Drawing.Size(560, 18)
$progressBar.Style = 'Marquee'
$progressBar.MarqueeAnimationSpeed = 0
$form.Controls.Add($progressBar)

$lblLog = New-Object System.Windows.Forms.Label
$lblLog.Text = 'Nhat ky:'
$lblLog.Location = New-Object System.Drawing.Point(20, 288)
$lblLog.AutoSize = $true
$form.Controls.Add($lblLog)

$txtLog = New-Object System.Windows.Forms.TextBox
$txtLog.Multiline = $true
$txtLog.ScrollBars = 'Vertical'
$txtLog.ReadOnly = $true
$txtLog.Location = New-Object System.Drawing.Point(20, 310)
$txtLog.Size = New-Object System.Drawing.Size(560, 280)
$txtLog.Font = New-Object System.Drawing.Font('Consolas', 9)
$txtLog.BackColor = [System.Drawing.Color]::Black
$txtLog.ForeColor = [System.Drawing.Color]::FromArgb(0, 255, 90)
$form.Controls.Add($txtLog)

$lblStatus = New-Object System.Windows.Forms.Label
$lblStatus.Text = 'San sang.'
$lblStatus.Location = New-Object System.Drawing.Point(20, 600)
$lblStatus.AutoSize = $true
$form.Controls.Add($lblStatus)

# ============================================================
# Quet danh sach o dia + tu dong nhan dien the moi cam vao
# ============================================================

function Get-RemovableDriveIds {
    try {
        return @(Get-CimInstance -ClassName Win32_LogicalDisk -ErrorAction Stop |
            Where-Object { $_.DriveType -eq 2 -or $_.DriveType -eq 3 } |
            Select-Object -ExpandProperty DeviceID)
    }
    catch {
        return @()
    }
}

function Update-DriveList {
    $cmbDrive.Items.Clear()
    try {
        $drives = Get-CimInstance -ClassName Win32_LogicalDisk -ErrorAction Stop |
            Where-Object { $_.DriveType -eq 2 -or $_.DriveType -eq 3 }
        foreach ($d in $drives) {
            $volName = if ($d.VolumeName) { $d.VolumeName } else { '(khong ten)' }
            $sizeGB = if ($d.Size) { [Math]::Round($d.Size / 1GB, 1) } else { 0 }
            [void]$cmbDrive.Items.Add("$($d.DeviceID)\  -  $volName ($sizeGB GB)")
        }
    }
    catch {
        Write-Warning "Khong quet duoc danh sach o dia: $($_.Exception.Message)"
    }
    if ($cmbDrive.Items.Count -gt 0) { $cmbDrive.SelectedIndex = 0 }
}
Update-DriveList
$script:knownDriveIds = Get-RemovableDriveIds

# ============================================================
# Quet nhanh 1 the (chi doc) tren luong nen - hien so file/dung luong/ETA
# ============================================================

$scanSyncHash = [hashtable]::Synchronized(@{
    IsRunning    = $false
    IsDone       = $false
    Summary      = $null
    ErrorMessage = $null
})
$script:scanPs = $null
$script:scanHandle = $null
$script:scanRunspace = $null
$script:lastCardSummary = $null

function Get-SelectedDest {
    if ($radDrive.Checked) { return 'drive' }
    if ($radOnedrive.Checked) { return 'onedrive' }
    return 'both'
}

function Update-EtaDisplay {
    if (-not $script:lastCardSummary) { return }
    $etaSec = Get-EstimatedDurationSeconds -Summary $script:lastCardSummary -Config $Config -Dest (Get-SelectedDest)
    $etaMin = [Math]::Round($etaSec / 60, 1)
    $lblEta.Text = "Uoc tinh thoi gian: ~$etaMin phut (gia dinh toc do doc the/mang, co the chenh lech nhieu tuy thuc te)"
}

function Start-CardScan {
    param([string]$CardDrivePath)

    if ($scanSyncHash.IsRunning -or $syncHash.IsRunning) { return }

    $scanSyncHash.IsRunning = $true
    $scanSyncHash.IsDone = $false
    $scanSyncHash.Summary = $null
    $scanSyncHash.ErrorMessage = $null

    $lblCardInfo.Text = "Dang quet the ($CardDrivePath)..."
    $lblEta.Text = ''

    $runspace = [runspacefactory]::CreateRunspace()
    $runspace.Open()
    $runspace.SessionStateProxy.SetVariable('scanSyncHash', $scanSyncHash)
    $runspace.SessionStateProxy.SetVariable('scriptRoot', $scriptRoot)
    $runspace.SessionStateProxy.SetVariable('cardDrivePath', $CardDrivePath)

    $ps = [powershell]::Create()
    $ps.Runspace = $runspace
    [void]$ps.AddScript({
        . (Join-Path $scriptRoot 'ingest.functions.ps1')
        try {
            $Config = Get-JsonFile -Path (Join-Path $scriptRoot 'ingest.config.json')
            $summary = Get-CardSummary -CardDrive $cardDrivePath -Config $Config
            $scanSyncHash.Summary = $summary
        }
        catch {
            $scanSyncHash.ErrorMessage = $_.Exception.Message
        }
        finally {
            $scanSyncHash.IsDone = $true
            $scanSyncHash.IsRunning = $false
        }
    })

    $script:scanPs = $ps
    $script:scanHandle = $ps.BeginInvoke()
    $script:scanRunspace = $runspace
}

function Get-DrivePathFromComboLabel {
    param([string]$Label)
    return (($Label -split '\\')[0] + '\')
}

$btnRefreshDrive.Add_Click({
    Update-DriveList
    $script:knownDriveIds = Get-RemovableDriveIds
})

$btnScanAgain.Add_Click({
    if ($null -eq $cmbDrive.SelectedItem) {
        [System.Windows.Forms.MessageBox]::Show('Chon o dia the nho truoc.', 'Thieu thong tin', 'OK', 'Warning') | Out-Null
        return
    }
    Start-CardScan -CardDrivePath (Get-DrivePathFromComboLabel -Label ([string]$cmbDrive.SelectedItem))
})

$cmbDrive.Add_SelectedIndexChanged({
    if ($cmbDrive.SelectedItem) {
        Start-CardScan -CardDrivePath (Get-DrivePathFromComboLabel -Label ([string]$cmbDrive.SelectedItem))
    }
})

$radDrive.Add_CheckedChanged({ Update-EtaDisplay })
$radOnedrive.Add_CheckedChanged({ Update-EtaDisplay })
$radBoth.Add_CheckedChanged({ Update-EtaDisplay })

# ============================================================
# Chay pipeline that tren luong nen (khong lam dong cua so)
# ============================================================

$syncHash = [hashtable]::Synchronized(@{
    LogLines     = New-Object System.Collections.Generic.List[string]
    IsRunning    = $false
    IsDone       = $false
    Success      = $false
    ErrorMessage = $null
})

$script:currentPs = $null
$script:currentHandle = $null
$script:currentRunspace = $null
$script:lastLogCount = 0

$btnStart.Add_Click({
    if ($syncHash.IsRunning) { return }

    if ([string]::IsNullOrWhiteSpace($txtProject.Text)) {
        [System.Windows.Forms.MessageBox]::Show('Nhap ten du an truoc.', 'Thieu thong tin', 'OK', 'Warning') | Out-Null
        return
    }
    if ($null -eq $cmbDrive.SelectedItem) {
        [System.Windows.Forms.MessageBox]::Show('Chon o dia the nho truoc (bam Lam moi neu chua thay).', 'Thieu thong tin', 'OK', 'Warning') | Out-Null
        return
    }

    $cardDrive = Get-DrivePathFromComboLabel -Label ([string]$cmbDrive.SelectedItem)
    $projectName = $txtProject.Text.Trim()
    $dest = Get-SelectedDest
    $skipUpload = $chkSkipUpload.Checked

    $syncHash.IsRunning = $true
    $syncHash.IsDone = $false
    $syncHash.Success = $false
    $syncHash.ErrorMessage = $null
    $syncHash.LogLines.Clear()
    $script:lastLogCount = 0
    $txtLog.Clear()
    $btnStart.Enabled = $false
    $btnStart.Text = 'Dang chay...'
    $lblStatus.Text = 'Dang xu ly, dung tat cua so...'
    $progressBar.MarqueeAnimationSpeed = 30

    $runspace = [runspacefactory]::CreateRunspace()
    $runspace.Open()
    $runspace.SessionStateProxy.SetVariable('syncHash', $syncHash)
    $runspace.SessionStateProxy.SetVariable('scriptRoot', $scriptRoot)
    $runspace.SessionStateProxy.SetVariable('cardDrive', $cardDrive)
    $runspace.SessionStateProxy.SetVariable('projectName', $projectName)
    $runspace.SessionStateProxy.SetVariable('dest', $dest)
    $runspace.SessionStateProxy.SetVariable('skipUpload', $skipUpload)

    $ps = [powershell]::Create()
    $ps.Runspace = $runspace

    [void]$ps.AddScript({
        . (Join-Path $scriptRoot 'ingest.functions.ps1')

        function Write-GuiLog {
            param([string]$Text)
            $syncHash.LogLines.Add($Text)
        }

        try {
            $configPath = Join-Path $scriptRoot 'ingest.config.json'
            $secretsPath = Join-Path $scriptRoot 'ingest.secrets.json'

            $Config = Get-JsonFile -Path $configPath
            if (-not $Config) { throw "Khong tim thay ingest.config.json canh script." }
            $Secrets = Get-JsonFile -Path $secretsPath
            if (-not $Secrets) {
                Write-GuiLog "Chua co ingest.secrets.json - chi bao bang Windows toast, khong gui Telegram."
            }

            $logFolder = Join-Path $scriptRoot $Config.logFolderName
            New-Item -ItemType Directory -Path $logFolder -Force | Out-Null
            $safeProjectName = ($projectName -replace '[\\/:*?"<>|]', '_')
            $LogFile = Join-Path $logFolder "$(Get-Date -Format 'yyyyMMdd_HHmmss')_$($safeProjectName).log"
            New-Item -ItemType File -Path $LogFile -Force | Out-Null

            Write-GuiLog "=== Bat dau do the: $projectName ($cardDrive) ==="

            $Paths = New-ProjectFolder -Config $Config -ShootDate (Get-Date) -ProjectName $projectName
            Write-GuiLog "Da tao thu muc du an: $($Paths.ProjectFolder)"

            Write-GuiLog "Dang quet va copy tu the nho (co the mat vai phut voi the dung luong lon)..."
            $summary = Copy-CardContents -CardDrive $cardDrive -Paths $Paths -Config $Config -LogFile $LogFile

            Test-CopyIntegrity -Summary $summary -LogFile $LogFile
            Write-GuiLog "Xac minh OK: $($summary.CopiedFileCount) file moi, $($summary.SkippedDuplicate) da co san, $($summary.RenamedCollision) trung ten da doi ten."
            Write-GuiLog "-> AN TOAN de format the nho."

            Write-GuiLog "Dang dong goi goc/ (che do store, khong nen that)..."
            $archiveInfo = Compress-RawFootage -Paths $Paths -Config $Config -ProjectName $projectName -LogFile $LogFile
            Write-GuiLog "Da dong goi xong: $($archiveInfo.Name) ($([Math]::Round($archiveInfo.Length / 1GB, 2)) GB)"

            $uploadResults = $null
            if (-not $skipUpload) {
                Write-GuiLog "Dang upload len cloud ($dest)..."
                $uploadResults = Publish-ToCloud -ArchivePath $archiveInfo.FullName -Dest $dest -Config $Config -LogFile $LogFile -Paths $Paths
                foreach ($r in $uploadResults) { Write-GuiLog "Da upload: $r" }
            }
            else {
                Write-GuiLog "Bo qua upload theo yeu cau."
            }

            $doneMsg = "$($summary.PhotoCount) anh, $($summary.VideoCount) video da do vao $($Paths.ProjectFolder)."
            if ($uploadResults) { $doneMsg += " Da upload: $($uploadResults -join ', ')" }
            Write-GuiLog $doneMsg

            try {
                Send-Notification -Title "Do the xong: $projectName" -Message $doneMsg -Secrets $Secrets
            }
            catch {
                Write-GuiLog "Canh bao: gui thong bao that bai - $($_.Exception.Message)"
            }

            $syncHash.Success = $true
        }
        catch {
            $syncHash.ErrorMessage = $_.Exception.Message
            Write-GuiLog "LOI: $($_.Exception.Message)"
            $syncHash.Success = $false
        }
        finally {
            $syncHash.IsDone = $true
            $syncHash.IsRunning = $false
        }
    })

    $script:currentPs = $ps
    $script:currentHandle = $ps.BeginInvoke()
    $script:currentRunspace = $runspace
})

# ============================================================
# Timer 1: doc log tu luong nen chay pipeline, cap nhat giao dien
# ============================================================

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 200
$timer.Add_Tick({
    if ($syncHash.LogLines.Count -gt $script:lastLogCount) {
        for ($i = $script:lastLogCount; $i -lt $syncHash.LogLines.Count; $i++) {
            $txtLog.AppendText("$($syncHash.LogLines[$i])`r`n")
        }
        $script:lastLogCount = $syncHash.LogLines.Count
    }

    if ($syncHash.IsDone) {
        $progressBar.MarqueeAnimationSpeed = 0
        $btnStart.Enabled = $true
        $btnStart.Text = 'Bat dau do the'

        if ($syncHash.Success) {
            $lblStatus.Text = 'Xong.'
            [System.Windows.Forms.MessageBox]::Show('Da do the xong!', 'Thanh cong', 'OK', 'Information') | Out-Null
        }
        else {
            $lblStatus.Text = 'Loi - xem nhat ky ben tren.'
            [System.Windows.Forms.MessageBox]::Show("Co loi xay ra:`n$($syncHash.ErrorMessage)", 'That bai', 'OK', 'Error') | Out-Null
        }

        if ($script:currentPs) {
            try { $script:currentPs.EndInvoke($script:currentHandle) } catch { }
            $script:currentPs.Dispose()
            $script:currentRunspace.Close()
            $script:currentPs = $null
            $script:currentRunspace = $null
        }

        $syncHash.IsDone = $false
    }

    # ---- ket qua quet the (neu co) ----
    if ($scanSyncHash.IsDone) {
        if ($scanSyncHash.Summary) {
            $s = $scanSyncHash.Summary
            $totalGB = [Math]::Round($s.TotalBytes / 1GB, 2)
            if ($s.FileCount -eq 0) {
                $lblCardInfo.Text = 'The nho trong, khong co file nao.'
                $lblEta.Text = ''
                $script:lastCardSummary = $null
            }
            else {
                $lblCardInfo.Text = "The nho: $($s.FileCount) file ($($s.PhotoCount) anh, $($s.VideoCount) video) - $totalGB GB"
                $script:lastCardSummary = $s
                Update-EtaDisplay
            }
        }
        else {
            $lblCardInfo.Text = "Loi quet the: $($scanSyncHash.ErrorMessage)"
            $lblEta.Text = ''
            $script:lastCardSummary = $null
        }

        if ($script:scanPs) {
            try { $script:scanPs.EndInvoke($script:scanHandle) } catch { }
            $script:scanPs.Dispose()
            $script:scanRunspace.Close()
            $script:scanPs = $null
            $script:scanRunspace = $null
        }
        $scanSyncHash.IsDone = $false
    }

    # ---- tu dong nhan dien the moi cam vao ----
    if (-not $syncHash.IsRunning -and -not $scanSyncHash.IsRunning) {
        $currentDrives = Get-RemovableDriveIds
        $newDrives = @($currentDrives | Where-Object { $script:knownDriveIds -notcontains $_ })
        if ($newDrives.Count -gt 0) {
            Update-DriveList
            $matchLabel = $cmbDrive.Items | Where-Object { $_ -like "$($newDrives[0])*" } | Select-Object -First 1
            if ($matchLabel) {
                $cmbDrive.SelectedItem = $matchLabel
            }
            $lblStatus.Text = "Phat hien the nho moi: $($newDrives[0])"
            Start-CardScan -CardDrivePath "$($newDrives[0])\"
        }
        $script:knownDriveIds = $currentDrives
    }
})
$timer.Start()

$form.Add_FormClosing({
    if ($syncHash.IsRunning) {
        $result = [System.Windows.Forms.MessageBox]::Show(
            'Dang do the do dang. Dong cua so co the lam gian doan qua trinh copy/upload. Van dong?',
            'Canh bao', 'YesNo', 'Warning')
        if ($result -eq 'No') {
            $_.Cancel = $true
        }
    }
})

if ($cmbDrive.SelectedItem) {
    Start-CardScan -CardDrivePath (Get-DrivePathFromComboLabel -Label ([string]$cmbDrive.SelectedItem))
}

[void]$form.ShowDialog()
