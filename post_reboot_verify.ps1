# Post-reboot verification script for YVF
# Writes a log to post_reboot_verify_log.txt in the repository.
$RepoPath = "C:\Users\User\new\yona_vanguard_futures"
$Log = Join-Path $RepoPath 'post_reboot_verify_log.txt'
"=== Post-reboot verify started: $(Get-Date -Format o) ===" | Out-File -FilePath $Log -Encoding utf8 -Append

function Log { param($m) $m | Out-File -FilePath $Log -Encoding utf8 -Append }

try {
    Log "[1] Running: wsl --update"
    wsl --update 2>&1 | ForEach-Object { Log "WSL: $_" }
} catch { Log "wsl --update failed: $_" }

try {
    Log "[2] Attempting to start Docker Desktop (if installed)"
    $dockerDesktopPath = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
    if (Test-Path $dockerDesktopPath) {
        Start-Process -FilePath $dockerDesktopPath -ErrorAction SilentlyContinue
        Log "Started Docker Desktop process"
    } else {
        Log "Docker Desktop not found at $dockerDesktopPath"
    }
} catch { Log "Start-Process Docker Desktop failed: $_" }

# Wait up to 300s for docker to become available
$dockerOk = $false
$start = Get-Date
$timeout = 300
Log "[3] Waiting up to $timeout seconds for Docker daemon..."
while ( ((Get-Date) - $start).TotalSeconds -lt $timeout -and -not $dockerOk ) {
    try {
        docker info 2>&1 | ForEach-Object { Log "docker: $_" }
        if ($LASTEXITCODE -eq 0) { $dockerOk = $true; Log "docker is available"; break }
    } catch { Log "docker check error: $_" }
    Start-Sleep -Seconds 3
}
if (-not $dockerOk) { Log "docker did not become available within $timeout seconds" }

# Run integration pytest (requires Python launcher in PATH)
try {
    Log "[4] Running pytest integration test"
    $pyCmd = 'py -3 -m pytest engine_backend/tests/integration/test_redis_e2e.py -q'
    Log "Running: $pyCmd"
    $proc = Start-Process -FilePath 'py' -ArgumentList '-3','-m','pytest','engine_backend/tests/integration/test_redis_e2e.py','-q' -NoNewWindow -RedirectStandardOutput "$Log" -RedirectStandardError "$Log" -PassThru -Wait -ErrorAction SilentlyContinue
    if ($proc.ExitCode -eq 0) { Log "pytest integration succeeded (exit 0)" } else { Log "pytest integration exit code: $($proc.ExitCode)" }
} catch { Log "pytest run failed: $_" }

Log "=== Post-reboot verify finished: $(Get-Date -Format o) ==="

# Remove startup trigger (the .bat) so it doesn't run again
try {
    $startupBat = Join-Path $env:APPDATA 'Microsoft\\Windows\\Start Menu\\Programs\\Startup\\YVF_post_reboot_verify.bat'
    if (Test-Path $startupBat) { Remove-Item -LiteralPath $startupBat -Force -ErrorAction SilentlyContinue; Log "Removed startup bat: $startupBat" }
} catch { Log "Failed to remove startup bat: $_" }
