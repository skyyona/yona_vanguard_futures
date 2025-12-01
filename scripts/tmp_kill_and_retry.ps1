Set-Location 'C:\Users\User\new\yona_vanguard_futures'
$lockfile = '.\results\lock_check_after_inplace.txt'
$log = '.\results\sanitize_kill_log.txt'
("Kill-run started: {0}" -f (Get-Date).ToString('o')) | Out-File $log -Encoding utf8
if (-not (Test-Path $lockfile)) {
  ("Lock file not found: {0}" -f $lockfile) | Out-File $log -Append -Encoding utf8
  Write-Output ("Lock file not found: {0}" -f $lockfile)
  exit 0
}
$locked = Select-String -Path $lockfile -Pattern '^LOCKED:' | ForEach-Object { $_.Line -replace '^LOCKED:\s*','' }
if (-not $locked) {
  ("No locked files listed in {0}" -f $lockfile) | Out-File $log -Append -Encoding utf8
  Write-Output "No locked files"
  exit 0
}
$handleCmd = Get-Command handle.exe -ErrorAction SilentlyContinue
if ($handleCmd) {
  ("handle.exe present: {0}" -f $($handleCmd.Path)) | Out-File $log -Append -Encoding utf8
  foreach ($f in $locked) {
    ("Checking handles for: {0}" -f $f) | Out-File $log -Append -Encoding utf8
    $hraw = & $handleCmd.Path -accepteula -nobanner $f 2>&1
    if ($hraw -and ($hraw -match 'pid:')) {
      $matches = $hraw | Select-String -Pattern '([^\s]+)\s+pid:\s*(\d+)' | ForEach-Object { $_.Matches[0].Groups[1].Value + ',' + $_.Matches[0].Groups[2].Value }
      foreach ($m in $matches) {
         $parts = $m -split ','
         $mn = $parts[0]; $pid = [int]$parts[1]
        Out-File -FilePath $log -Append -InputObject (("Killing process {0} ({1}) holding {2}" -f $mn, $pid, $f)) -Encoding utf8
        try {
          Stop-Process -Id $pid -Force
          Out-File -FilePath $log -Append -InputObject (("Stopped {0} ({1})" -f $pid, $mn)) -Encoding utf8
        } catch {
          Out-File -FilePath $log -Append -InputObject (("Failed to stop {0}: {1}" -f $pid, ($_ | Out-String))) -Encoding utf8
        }
      }
    } else {
      $hrawStr = $hraw | Out-String
      Out-File -FilePath $log -Append -InputObject (("No handle info for {0} (handle output length: {1})" -f $f, $hrawStr.Length)) -Encoding utf8
    }
  }
} else {
  ("handle.exe not found; falling back to candidate kill") | Out-File $log -Append -Encoding utf8
  $cands = Get-Process | Where-Object { $_.ProcessName -match 'EXCEL|Code|python|pythonw|powershell|pwsh|node|RStudio' } | Where-Object { $_.ProcessName -notin @('explorer','System') }
  foreach ($p in $cands) {
    ("Attempting to stop {0} ({1})" -f $p.ProcessName, $p.Id) | Out-File $log -Append -Encoding utf8
    try { Stop-Process -Id $p.Id -Force; (("Stopped {0} ({1})" -f $p.Id, $p.ProcessName)) | Out-File $log -Append -Encoding utf8 } catch { (("Failed to stop {0}: {1}" -f $p.Id, $_)) | Out-File $log -Append -Encoding utf8 }
  }
}
("Waiting 2s for OS to release handles") | Out-File $log -Append -Encoding utf8
Start-Sleep -Seconds 2
# pick the most recent backup dir under results_backups
$rb = Get-ChildItem -Path '.\results_backups' -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1
if ($rb) { $backup = $rb.FullName } else { $backup = '' }
("Retrying sanitizer (whole results dir) with backup {0}" -f $backup) | Out-File $log -Append -Encoding utf8
try {
  if ($backup -ne '') {
    # run sanitizer and append output to the kill log
    & python .\scripts\sanitize_results.py --results-dir results --inplace --backup-dir $backup 2>&1 | Out-File $log -Append -Encoding utf8
  } else {
    ("No backup directory found; aborting sanitizer run") | Out-File $log -Append -Encoding utf8
  }
  "Sanitizer run completed" | Out-File $log -Append
} catch {
  ("Sanitizer run failed to start: {0}" -f $_) | Out-File $log -Append -Encoding utf8
}
(("Kill-run completed: {0}" -f (Get-Date).ToString('o'))) | Out-File $log -Append -Encoding utf8
Write-Output ("Wrote kill/log to {0}" -f $log)
