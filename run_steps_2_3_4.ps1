$log='C:\Users\User\new\yona_vanguard_futures\post_reboot_verify_log.txt'
function Log($m){ (Get-Date).ToString('o') + ' ' + $m | Out-File -FilePath $log -Append -Encoding utf8 }
Log '=== Automated run (2->3->4) started ==='

# Step 2: Start Docker Desktop if present
Log 'Step 2: Start Docker Desktop (if present)'
$dockerPath = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
if (Test-Path $dockerPath) {
    try {
        Start-Process -FilePath $dockerPath -ErrorAction Stop
        Log 'Started Docker Desktop process'
    } catch {
        Log ('Failed to start Docker Desktop: ' + $_.Exception.Message)
    }
} else {
    Log ('Docker Desktop not found at ' + $dockerPath)
}

# Step 3: Run WSL update
Log 'Step 3: Run wsl --update'
try {
    wsl --update 2>&1 | ForEach-Object { Log ('WSL: ' + $_) }
} catch {
    Log ('wsl --update failed: ' + $_.Exception.Message)
}

# Step 3.5: Wait up to 300s for docker daemon
Log 'Step 3.5: Wait up to 300s for docker daemon to respond'
$dockerOk = $false
$start = Get-Date
while ( ((Get-Date) - $start).TotalSeconds -lt 300 -and -not $dockerOk ) {
    try {
        docker info 2>&1 | ForEach-Object { Log ('docker: ' + $_) }
        if ($LASTEXITCODE -eq 0) {
            $dockerOk = $true
            Log 'docker is available'
            break
        }
    } catch {
        Log ('docker check error: ' + $_.Exception.Message)
    }
    Start-Sleep -Seconds 3
}
if (-not $dockerOk) { Log ('docker did not become available within 300 seconds') }

# Step 4: Run pytest integration test
Log 'Step 4: Run pytest integration test'
try {
    py -3 -m pytest engine_backend/tests/integration/test_redis_e2e.py -q 2>&1 | ForEach-Object { Log ('PYTEST: ' + $_) }
} catch {
    Log ('pytest run failed: ' + $_.Exception.Message)
}

Log '=== Automated run (2->3->4) finished ==='
