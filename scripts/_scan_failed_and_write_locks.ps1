# Scan the latest retry summary for failed files and run handle.exe on each; produce results\lock_check_after_inplace.txt with LOCKED: lines
Set-Location 'C:\Users\User\new\yona_vanguard_futures'
$summary = Get-ChildItem -Path .\results -Filter 'sanitize_retry_summary_*.txt' -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $summary) { Write-Output 'No retry summary found'; exit 0 }
$out = '.\results\lock_check_after_inplace.txt'
Remove-Item -Path $out -ErrorAction SilentlyContinue
$handleCmd = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'tools\handle.exe'
if (-not (Test-Path $handleCmd)) { Write-Output 'handle.exe not found in scripts\tools; will not detect locks'; exit 0 }
Get-Content $summary | ForEach-Object {
    if ($_ -match '^\(inplace\)\s+(.*)') {
        $rel = $Matches[1]
        # normalize path: replace ..\ with repo root
        $full = Resolve-Path -LiteralPath (Join-Path (Get-Location) $rel) -ErrorAction SilentlyContinue
        if (-not $full) { $full = Join-Path (Get-Location) $rel }
        $fullPath = $full.ToString()
        $h = & $handleCmd -accepteula -nobanner $fullPath 2>&1
        $hstr = $h -join "`n"
        if ($hstr -and ($hstr -match 'pid:\s*\d+')) {
            ('LOCKED: {0}' -f $fullPath) | Out-File -FilePath $out -Append -Encoding utf8
        }
    }
}
Write-Output ("Wrote lock-scan to {0}" -f $out)