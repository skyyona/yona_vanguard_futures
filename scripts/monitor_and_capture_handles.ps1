param(
  [int]$Seconds = 30,
  [int]$Interval = 1,
  [int]$Top = 20
)

Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
$repoRoot = Resolve-Path -Path '..' | Select-Object -ExpandProperty Path
$resultsDir = Join-Path $repoRoot 'results'
if (-not (Test-Path $resultsDir)) { New-Item -Path $resultsDir -ItemType Directory -Force | Out-Null }

$ts = (Get-Date).ToString('yyyyMMddTHHmmss')
$outCsv = Join-Path $resultsDir ("handle_capture_{0}.csv" -f $ts)
$outSummary = Join-Path $resultsDir ("captured_lock_processes_{0}.txt" -f $ts)

$handlePath = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'tools\handle.exe'
if (-not (Test-Path $handlePath)) {
  "handle.exe not found at {0}. Please run scripts\_download_handle.ps1 first." -f $handlePath | Out-File -FilePath $outSummary -Encoding utf8
  Write-Output "handle.exe not found; aborting. See $outSummary"
  exit 1
}

# get top failed file paths from latest retry summary
$summary = Get-ChildItem -Path $resultsDir -Filter 'sanitize_retry_summary_*.txt' -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $summary) { "No retry summary found in $resultsDir" | Out-File -FilePath $outSummary -Encoding utf8; Write-Output 'No retry summary'; exit 1 }

$lines = Get-Content -Path $summary.FullName | Select-String -Pattern '^\(inplace\)\s+(.*)' | ForEach-Object { $_.Matches[0].Groups[1].Value }
if (-not $lines) { "No failed (inplace) entries found in $($summary.FullName)" | Out-File -FilePath $outSummary -Encoding utf8; Write-Output 'No failed entries'; exit 0 }

$candidates = $lines | Select-Object -First $Top | ForEach-Object {
    $rel = $_ -replace '^\.\.\\', ''
    $full = Join-Path $repoRoot $rel
    $full
}

# header for CSV
"File,PID,HandleOutput" | Out-File -FilePath $outCsv -Encoding utf8

$end = (Get-Date).AddSeconds($Seconds)
Write-Output ("Monitoring {0} files for {1}s (interval {2}s): writing captures to {3}" -f $candidates.Count, $Seconds, $Interval, $outCsv)

$captures = @()
while ((Get-Date) -lt $end) {
  foreach ($f in $candidates) {
    if (-not (Test-Path $f)) { continue }
    try {
      $hraw = & $handlePath -accepteula -nobanner $f 2>&1
    } catch {
      $hraw = ($_ | Out-String)
    }
    $htext = ($hraw -join "`n").Trim()
    if ($htext -match 'pid:\s*(\d+)') {
      # capture all pid matches
      $matches = ([regex]::Matches($htext, '([\S]+)\s+pid:\s*(\d+)'))
      foreach ($m in $matches) {
        $pname = $m.Groups[1].Value;
        $pid = $m.Groups[2].Value;
        $line = '"{0}",{1},"{2}"' -f $f,$pid,($htext -replace '"','""')
        $line | Out-File -FilePath $outCsv -Append -Encoding utf8
        $captures += [pscustomobject]@{ File = $f; PID = [int]$pid; ProcessName = $pname; HandleOutput = $htext }
      }
    }
  }
  Start-Sleep -Seconds $Interval
}

if (-not $captures) {
  "No handles captured during monitoring." | Out-File -FilePath $outSummary -Encoding utf8
  Write-Output 'No handles captured'
  exit 0
}

# summarize unique PIDs
$uniq = $captures | Sort-Object PID -Unique
"Captured lock-holder processes:" | Out-File -FilePath $outSummary -Encoding utf8
foreach ($u in $uniq) {
  $pid = $u.PID
  $w = Get-WmiObject Win32_Process -Filter ("ProcessId={0}" -f $pid) -ErrorAction SilentlyContinue
  if ($w) {
    $exe = $w.ExecutablePath
    $cmd = $w.CommandLine
  } else { $exe = ''; $cmd = '' }
  ("PID={0} Name={1} Executable={2} CommandLine={3}" -f $pid, $u.ProcessName, $exe, $cmd) | Out-File -FilePath $outSummary -Append -Encoding utf8
}

Write-Output ("Wrote captures to {0} and summary to {1}" -f $outCsv, $outSummary)
exit 0
