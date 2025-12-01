# Fallback: robocopy with /COPY:DAT and /E, then run sanitizer on the copied tree
$repo = 'C:\Users\User\new\yona_vanguard_futures'
Set-Location $repo
$ts = (Get-Date).ToString('yyyyMMddTHHmmssZ')
$workDir = Join-Path '.\vss_tmp' $ts
New-Item -ItemType Directory -Path $workDir -Force | Out-Null
$dest = Join-Path $workDir 'results_copy'
New-Item -ItemType Directory -Path $dest -Force | Out-Null
$robOut = Join-Path $workDir 'robocopy_copy_dat_out.txt'
# Run robocopy with /COPY:DAT /E
robocopy '.\results' $dest /E /COPY:DAT /R:2 /W:5 | Out-File -FilePath $robOut -Encoding utf8
Write-Host "Robocopy finished. Log: $robOut"

# Run sanitizer on the copy
$backupDir = Join-Path '.\results_backups' ("copy_dat_backup_$ts")
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
$sanitizeOut = Join-Path $workDir 'sanitize_copy_dat_out.txt'
& python scripts\sanitize_results.py --results-dir $dest --backup-dir $backupDir 2>&1 | Out-File -FilePath $sanitizeOut -Encoding utf8
Write-Host "Sanitizer finished. Log: $sanitizeOut"
Write-Host "Workdir: $workDir"
