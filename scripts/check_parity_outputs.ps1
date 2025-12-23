# Check script: ensures parity_dir exists and parity_report.json files are properly located
$root = Get-Location
try {
    $py = "C:/Users/User/AppData/Local/Programs/Python/Python313/python.exe"
    $code = @'
from scripts import output_config, os
p = output_config.parity_dir()
print(p)
'@
    $pdir = & $py -c $code 2>$null
    if (-not $pdir) { Write-Error "parity_dir() returned empty"; exit 2 }
    $pdir = $pdir.Trim()
    Write-Host "parity_dir -> $pdir"
    $bad = @()
    Get-ChildItem -Path . -Filter parity_report.json -Recurse -Force | ForEach-Object {
        $full = $_.FullName
        if (-not ($full.StartsWith($pdir) -or $full.StartsWith((Join-Path $pdir 'legacy')))) {
            $bad += $full
        }
    }
    if ($bad.Count -gt 0) {
        Write-Error "Found parity_report.json outside parity_dir:`n$($bad -join "`n")"
        exit 3
    }
    Write-Host "All parity_report.json files are under parity_dir or legacy."
    exit 0
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
