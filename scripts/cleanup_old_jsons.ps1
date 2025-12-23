Param(
    [string]$Root = (Join-Path -Path $PSScriptRoot -ChildPath "..\outputs"),
    [int]$Days = 7,
    [switch]$Delete
)

$excludePatterns = @('\\.venv','\\venv','\\env','\\.git','node_modules','site-packages','__pycache__','vss_tmp')
$cutoff = (Get-Date).AddDays(-$Days)

$filesRaw = Get-ChildItem -Path $Root -Filter '*.json' -Recurse -File -ErrorAction SilentlyContinue
$files = $filesRaw | Where-Object {
    $_.LastWriteTime -lt $cutoff
} | Where-Object {
    $keep = $true
    foreach ($pat in $excludePatterns) {
        if ($pat -and ($_.FullName -match $pat)) { $keep = $false; break }
    }
    $keep
}

if (-not $files) {
    Write-Output "No JSON files older than $Days days found under $Root."
    exit 0
}

Write-Output ("Found {0} JSON files older than {1} days under {2}`n" -f $files.Count, $Days, $Root)
$files | Select-Object FullName, LastWriteTime | Format-Table -AutoSize

$logDir = Join-Path -Path $Root -ChildPath "outputs\cleanup_logs"
if (-not (Test-Path $logDir)) { New-Item -Path $logDir -ItemType Directory | Out-Null }
$logFile = Join-Path $logDir ("cleanup_$(Get-Date -Format 'yyyyMMdd_HHmmss').log")

if ($Delete) {
    Write-Output "Deleting files..."
    $files | ForEach-Object {
        try {
            Remove-Item -LiteralPath $_.FullName -Force -ErrorAction Stop
            "DELETED: $($_.FullName) | $($_.LastWriteTime)" | Out-File -FilePath $logFile -Append -Encoding utf8
        } catch {
            "FAILED: $($_.FullName) | $_" | Out-File -FilePath $logFile -Append -Encoding utf8
        }
    }
    Write-Output "Deletion completed. Log: $logFile"
} else {
    Write-Output "Dry-run: no files were deleted. To actually delete, re-run with -Delete."
    Write-Output "Example: powershell -ExecutionPolicy Bypass -File .\scripts\cleanup_old_jsons.ps1 -Days 7 -Delete"
    Write-Output "Dry-run also logs WhatIf output to console only."
}
