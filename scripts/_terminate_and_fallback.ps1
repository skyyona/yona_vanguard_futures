# Terminate approved PID 4508 (graceful then force) and run non-elevated robocopy fallback + sanitizer
param()

$repo = 'C:\Users\User\new\yona_vanguard_futures'
Set-Location $repo

$ts = (Get-Date).ToString('yyyyMMddTHHmmssZ')
$workDir = Join-Path '.\vss_tmp' $ts
New-Item -ItemType Directory -Path $workDir -Force | Out-Null

# Pre-backup of results
$backupPre = Join-Path '.\results_backups' ("pre_kill_backup_$ts")
New-Item -ItemType Directory -Path $backupPre -Force | Out-Null
$robPreOut = Join-Path $workDir 'robocopy_backup_pre.txt'
robocopy '.\results' $backupPre /MIR /COPYALL /R:2 /W:5 | Out-File -FilePath $robPreOut -Encoding utf8

$killLog = Join-Path '.\results' ("kill_log_$ts.txt")
"$(Get-Date -Format o) Starting termination sequence for PID 4508" | Out-File -FilePath $killLog -Encoding utf8

# Attempt graceful stop
$proc = Get-Process -Id 4508 -ErrorAction SilentlyContinue
if ($proc) {
    "$(Get-Date -Format o) Found process 4508 (Name: $($proc.ProcessName)), attempting Stop-Process" | Out-File -FilePath $killLog -Append
    try {
        Stop-Process -Id 4508 -ErrorAction Stop
        "$(Get-Date -Format o) Stop-Process succeeded" | Out-File -FilePath $killLog -Append
    } catch {
        "$(Get-Date -Format o) Stop-Process failed: $_" | Out-File -FilePath $killLog -Append
    }
    Start-Sleep -Seconds 5
    $proc2 = Get-Process -Id 4508 -ErrorAction SilentlyContinue
    if ($proc2) {
        "$(Get-Date -Format o) Process still exists; forcing via taskkill" | Out-File -FilePath $killLog -Append
        cmd.exe /c "taskkill /F /PID 4508 /T" | Out-File -FilePath $killLog -Append
    } else {
        "$(Get-Date -Format o) Process stopped cleanly" | Out-File -FilePath $killLog -Append
    }
} else {
    "$(Get-Date -Format o) Process 4508 not found" | Out-File -FilePath $killLog -Encoding utf8
}

# Fallback copy via robocopy
$dest = Join-Path $workDir 'results_copy'
New-Item -ItemType Directory -Path $dest -Force | Out-Null
$robOut = Join-Path $workDir 'robocopy_out.txt'
robocopy '.\results' $dest /MIR /COPYALL /R:2 /W:5 | Out-File -FilePath $robOut -Encoding utf8

# Run sanitizer against the copied results
$backupDir = Join-Path '.\results_backups' ("vss_fallback_backup_$ts")
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
$sanitizeOut = Join-Path $workDir 'sanitize_out.txt'
python .\scripts\sanitize_results.py --results-dir $dest --inplace --backup-dir $backupDir 2>&1 | Out-File -FilePath $sanitizeOut -Encoding utf8

"$(Get-Date -Format o) Fallback run complete. Workdir: $workDir" | Out-File -FilePath (Join-Path $workDir 'run_complete.txt') -Encoding utf8

# write a short summary to results
$summary = @()
$summary += "Fallback run summary - $ts"
$summary += "Workdir: $workDir"
$summary += "Kill log: $killLog"
$summary += "Robocopy out: $robOut"
$summary += "Sanitize out: $sanitizeOut"
$summary | Out-File -FilePath (Join-Path '.\results' ("fallback_summary_$ts.txt")) -Encoding utf8

Exit 0
