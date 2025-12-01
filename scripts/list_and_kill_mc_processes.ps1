# Locate Python processes whose command-line mentions mc_test_runner.py or mc_robustness.py
Write-Output "Searching for Python processes referencing test/MC scripts..."

$matches = @()
Get-Process -Name python -ErrorAction SilentlyContinue | ForEach-Object {
    $pid = $_.Id
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$pid"
    if ($proc -and $proc.CommandLine -match 'mc_test_runner.py|mc_robustness.py') {
        $matches += $proc
    }
}

if ($matches.Count -eq 0) {
    Write-Output "No matching processes found."
    exit 0
}

Write-Output "Found the following matching processes:"
$matches | Select-Object ProcessId,CommandLine | Format-List

foreach ($p in $matches) {
    $pid = $p.ProcessId
    Write-Output "Attempting graceful stop of PID $pid..."
    try {
        Stop-Process -Id $pid -ErrorAction Stop
        Start-Sleep -Seconds 1
        $still = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($still) {
            Write-Output "PID $pid still running; forcing termination..."
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        } else {
            Write-Output "PID $pid terminated cleanly."
        }
    } catch {
        Write-Output ("Error stopping PID {0}: {1}" -f $pid, $_)
    }
}

Write-Output "Done."
