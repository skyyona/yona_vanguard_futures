# Check script: ensures parity_dir exists and parity_report.json files are properly located
$root = Get-Location
try {
    # Find a portable Python executable across platforms
    $candidates = @('python', 'python3', $env:PYTHON, $env:PYTHONHOME, $env:PYTHON_PATH)
    $py = $null
    foreach ($cand in $candidates) {
        if ([string]::IsNullOrWhiteSpace($cand)) { continue }
        try {
            if (Get-Command $cand -ErrorAction SilentlyContinue) { $py = $cand; break }
        } catch { }
    }
    if (-not $py) {
        Write-Error "No python executable found in PATH or common env vars. Set PATH or PYTHON env var."; exit 4
    }
    $code = "from scripts import output_config; print(output_config.parity_dir())"
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
