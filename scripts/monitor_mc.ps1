param(
    [Parameter(Mandatory=$true)] [int]$Pid,
    [Parameter(Mandatory=$false)] [string]$Symbol = 'pippinusdt'
)

$out = Join-Path -Path (Get-Location) -ChildPath "results\${Symbol}_mc_robustness_monitor.log"
Write-Output "Starting monitor for PID $Pid (symbol $Symbol). Log: $out"

function Write-Status {
    param($Tag)
    $now = Get-Date -Format o
    $proc = Get-Process -Id $Pid -ErrorAction SilentlyContinue
    if (-not $proc) {
        Add-Content -Path $out -Value "[$now] [$Tag] Process $Pid not found. Exiting monitor."
        return $false
    }
    $cpu = $proc.CPU
    $start = $proc.StartTime
    $children = Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $Pid } | Select-Object ProcessId,CommandLine

    $stderr = ''
    $stdout = ''
    $stderrPath = Join-Path -Path (Get-Location) -ChildPath "results\${Symbol}_mc_robustness_stderr.log"
    $stdoutPath = Join-Path -Path (Get-Location) -ChildPath "results\${Symbol}_mc_robustness_stdout.log"
    if (Test-Path $stderrPath) { $stderr = (Get-Content $stderrPath -Tail 20 -ErrorAction SilentlyContinue) -join "`n" }
    if (Test-Path $stdoutPath) { $stdout = (Get-Content $stdoutPath -Tail 20 -ErrorAction SilentlyContinue) -join "`n" }

    $lines = @()
    $lines += "[$now] [$Tag] PID=$Pid CPU=$cpu Start=$start Children=$(($children | Measure-Object).Count)"
    $lines += "--- STDERR (tail 20) ---"
    $lines += $stderr
    $lines += "--- STDOUT (tail 20) ---"
    $lines += $stdout
    $lines += "-------------------------"
    Add-Content -Path $out -Value $lines
    return $true
}

# Main loop: write status every 10 minutes until process exits
Add-Content -Path $out -Value "==== Monitor started $(Get-Date -Format o) for PID $Pid ===="
while ($true) {
    $ok = Write-Status -Tag 'heartbeat'
    if (-not $ok) { break }
    Start-Sleep -Seconds 600
}

Add-Content -Path $out -Value "==== Monitor finished $(Get-Date -Format o) for PID $Pid ===="
