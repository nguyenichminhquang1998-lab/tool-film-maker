<#
Helper doc rieng cho MCP server: quet 1 the nho (chi doc) va tra ve JSON
mot dong, de server.py (Python) doc va parse duoc.
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$CardDrive,

    [string]$Dest = 'both'
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $repoRoot 'ingest.functions.ps1')

try {
    if (-not $CardDrive.EndsWith('\')) {
        $CardDrive = "$CardDrive\"
    }

    $Config = Get-JsonFile -Path (Join-Path $repoRoot 'ingest.config.json')
    if (-not $Config) { throw "Khong tim thay ingest.config.json" }

    $summary = Get-CardSummary -CardDrive $CardDrive -Config $Config
    $etaSec = Get-EstimatedDurationSeconds -Summary $summary -Config $Config -Dest $Dest

    $result = [PSCustomObject]@{
        ok               = $true
        fileCount        = $summary.FileCount
        photoCount       = $summary.PhotoCount
        videoCount       = $summary.VideoCount
        totalBytes       = $summary.TotalBytes
        totalGB          = [Math]::Round($summary.TotalBytes / 1GB, 2)
        estimatedSeconds = $etaSec
        estimatedMinutes = [Math]::Round($etaSec / 60, 1)
    }
}
catch {
    $result = [PSCustomObject]@{
        ok    = $false
        error = $_.Exception.Message
    }
}

$result | ConvertTo-Json -Compress
