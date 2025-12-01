Param(
    [int]$MaxAttempts = 5,
    [int]$DelaySeconds = 5
)

Set-Location $PSScriptRoot
$timestamp = Get-Date -Format "yyyyMMddTHHmmss"
$backup = Join-Path -Path "..\results_backups" -ChildPath $timestamp
New-Item -ItemType Directory -Force -Path $backup | Out-Null
$log = Join-Path -Path "..\results" -ChildPath ("sanitize_retry_log_{0}.txt" -f $timestamp)
$summary = Join-Path -Path "..\results" -ChildPath ("sanitize_retry_summary_{0}.txt" -f $timestamp)
("Retry-run started: {0}" -f (Get-Date).ToString('o')) | Out-File $log -Encoding utf8
$attempt = 1
$failedFiles = @()

while ($attempt -le $MaxAttempts) {
    ("Attempt {0}: {1}" -f $attempt, (Get-Date).ToString('o')) | Out-File $log -Append -Encoding utf8
    # Build python argument list for sanitizer (avoid using the automatic $args variable)
    $pythonArgs = @('.\sanitize_results.py', '--results-dir', '..\results', '--inplace', '--backup-dir', $backup)
    # Ensure python is available
    $pyCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pyCmd) {
        ("python not found on PATH; aborting attempt {0}." -f $attempt) | Out-File $log -Append -Encoding utf8
        break
    }
    try {
        $outFile = Join-Path -Path "..\results" -ChildPath ("sanitize_retry_attempt_{0}_out.txt" -f $attempt)
        $errFile = Join-Path -Path "..\results" -ChildPath ("sanitize_retry_attempt_{0}_err.txt" -f $attempt)
        # Use shell redirection which is compatible with Windows PowerShell 5.1
        & python @pythonArgs 1> $outFile 2> $errFile
        # append outputs to the main log
        Get-Content $outFile -ErrorAction SilentlyContinue | Out-File $log -Append -Encoding utf8
        Get-Content $errFile -ErrorAction SilentlyContinue | Out-File $log -Append -Encoding utf8
        if ($LASTEXITCODE -ne 0) {
            ("python exited with code {0}" -f $LASTEXITCODE) | Out-File $log -Append -Encoding utf8
        }
    } catch {
        ("Failed to run python: {0}" -f $_) | Out-File $log -Append -Encoding utf8
        break
    }

    $content = Get-Content $log -Raw
    $matches = Select-String -InputObject $content -Pattern 'Error sanitizing.*? (.+?): \[WinError 32' -AllMatches
    if ($matches) {
        $failedFiles = $matches.Matches | ForEach-Object { $_.Groups[1].Value.Trim() } | Sort-Object -Unique
    } else {
        $failedFiles = @()
    }

    if (-not $failedFiles -or $failedFiles.Count -eq 0) {
        ("No WinError 32 failures detected on attempt {0}." -f $attempt) | Out-File $log -Append -Encoding utf8
        break
    }

    ("Attempt {0} found {1} failed files; will retry after backoff." -f $attempt, $failedFiles.Count) | Out-File $log -Append -Encoding utf8
    $failedFiles | Out-File $log -Append -Encoding utf8
    Start-Sleep -Seconds ($DelaySeconds * $attempt)
    $attempt++
}

("Retry-run completed: {0}" -f (Get-Date).ToString('o')) | Out-File $log -Append -Encoding utf8
("Summary for retry-run: {0}" -f $timestamp) | Out-File $summary -Encoding utf8
if ($failedFiles -and $failedFiles.Count -gt 0) {
    "Failed files (after $attempt attempts):" | Out-File $summary -Append -Encoding utf8
    $failedFiles | Out-File $summary -Append -Encoding utf8
} else {
    "All files sanitized or unchanged." | Out-File $summary -Append -Encoding utf8
}

# Also copy tail of log to a fixed location for quick access
Get-Content $log -Tail 200 | Out-File (Join-Path -Path "..\results" -ChildPath "sanitize_retry_log.txt") -Encoding utf8
Get-Content $summary | Out-File (Join-Path -Path "..\results" -ChildPath "sanitize_retry_summary.txt") -Encoding utf8
("Wrote logs: {0} and {1}" -f $log, $summary) | Out-File $log -Append -Encoding utf8
