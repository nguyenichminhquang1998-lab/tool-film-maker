<#
Giao dien cua so (GUI) cho pipeline do the - khong can go lenh.
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

# ============================================================
# Xay giao dien
# ============================================================

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Do the tu dong - tool-film-maker'
$form.Size = New-Object System.Drawing.Size(620, 600)
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

$btnRefreshDrive = New-Object System.Windows.Forms.Button
$btnRefreshDrive.Text = 'Lam moi'
$btnRefreshDrive.Location = New-Object System.Drawing.Point(460, 55)
$btnRefreshDrive.Size = New-Object System.Drawing.Size(120, 26)
$btnRefreshDrive.Add_Click({ Update-DriveList })
$form.Controls.Add($btnRefreshDrive)

$grpDest = New-Object System.Windows.Forms.GroupBox
$grpDest.Text = 'Upload len'
$grpDest.Location = New-Object System.Drawing.Point(20, 96)
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
$grpDest.Size = New-Object System.Drawing.Size(560, 50)

$btnStart = New-Object System.Windows.Forms.Button
$btnStart.Text = 'Bat dau do the'
$btnStart.Location = New-Object System.Drawing.Point(20, 156)
$btnStart.Size = New-Object System.Drawing.Size(560, 42)
$btnStart.Font = New-Object System.Drawing.Font($btnStart.Font.FontFamily, 12, [System.Drawing.FontStyle]::Bold)
$btnStart.BackColor = [System.Drawing.Color]::FromArgb(46, 125, 50)
$btnStart.ForeColor = [System.Drawing.Color]::White
$form.Controls.Add($btnStart)

$progressBar = New-Object System.Windows.Forms.ProgressBar
$progressBar.Location = New-Object System.Drawing.Point(20, 208)
$progressBar.Size = New-Object System.Drawing.Size(560, 18)
$progressBar.Style = 'Marquee'
$progressBar.MarqueeAnimationSpeed = 0
$form.Controls.Add($progressBar)

$lblLog = New-Object System.Windows.Forms.Label
$lblLog.Text = 'Nhat ky:'
$lblLog.Location = New-Object System.Drawing.Point(20, 234)
$lblLog.AutoSize = $true
$form.Controls.Add($lblLog)

$txtLog = New-Object System.Windows.Forms.TextBox
$txtLog.Multiline = $true
$txtLog.ScrollBars = 'Vertical'
$txtLog.ReadOnly = $true
$txtLog.Location = New-Object System.Drawing.Point(20, 256)
$txtLog.Size = New-Object System.Drawing.Size(560, 280)
$txtLog.Font = New-Object System.Drawing.Font('Consolas', 9)
$txtLog.BackColor = [System.Drawing.Color]::Black
$txtLog.ForeColor = [System.Drawing.Color]::FromArgb(0, 255, 90)
$form.Controls.Add($txtLog)

$lblStatus = New-Object System.Windows.Forms.Label
$lblStatus.Text = 'San sang.'
$lblStatus.Location = New-Object System.Drawing.Point(20, 545)
$lblStatus.AutoSize = $true
$form.Controls.Add($lblStatus)

# ============================================================
# Chay pipeline tren luong nen (khong lam dong cua so)
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

    $selectedDriveLabel = [string]$cmbDrive.SelectedItem
    $cardDrive = ($selectedDriveLabel -split '\\')[0] + '\'
    $projectName = $txtProject.Text.Trim()
    $dest = if ($radDrive.Checked) { 'drive' } elseif ($radOnedrive.Checked) { 'onedrive' } else { 'both' }
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
# Timer: doc log tu luong nen, cap nhat giao dien
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
            try {
                $script:currentPs.EndInvoke($script:currentHandle)
            }
            catch { }
            $script:currentPs.Dispose()
            $script:currentRunspace.Close()
            $script:currentPs = $null
            $script:currentRunspace = $null
        }

        $syncHash.IsDone = $false
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

[void]$form.ShowDialog()
