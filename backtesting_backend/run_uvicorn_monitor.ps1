param()

# Auto-restart monitor for backtesting uvicorn process.
# Detects a project venv under the repo root and runs uvicorn via that python.

$repoRoot = Resolve-Path "$PSScriptRoot\.." | Select-Object -ExpandProperty Path

# Candidate virtualenv python executables (checked in order)
$candidates = @(
    Join-Path $repoRoot ".venv_backtest\Scripts\python.exe",
    Join-Path $repoRoot ".venv_new\Scripts\python.exe",
    Join-Path $repoRoot ".venv\Scripts\python.exe",
    Join-Path $repoRoot "venv\Scripts\python.exe"
)

$python = $null
foreach ($p in $candidates) {
    if (Test-Path $p) { $python = $p; break }
}
if (-not $python) { $python = "python" }

$uvicornLog = Join-Path $repoRoot "backtesting_backend\logs\uvicorn.log"
$monitorLog = Join-Path $repoRoot "backtesting_backend\logs\uvicorn_monitor.log"

if (-not (Test-Path (Split-Path $uvicornLog -Parent))) { New-Item -ItemType Directory -Path (Split-Path $uvicornLog -Parent) | Out-Null }

Write-Output "Using python: $python" | Out-File -FilePath $monitorLog -Append -Encoding utf8

while ($true) {
    $startTs = Get-Date -Format o
    "$startTs - Starting uvicorn via $python" | Out-File -FilePath $monitorLog -Append -Encoding utf8

    $args = "-m uvicorn backtesting_backend.app_main:app --host 127.0.0.1 --port 8001 --log-level info"

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $python
    $startInfo.Arguments = $args
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.UseShellExecute = $false
    $startInfo.WorkingDirectory = $repoRoot

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $startInfo
    $proc.Start() | Out-Null

    # Stream output to uvicorn log
    $stdOut = $proc.StandardOutput
    $stdErr = $proc.StandardError

    while (-not $proc.HasExited) {
        try {
            if (-not $stdOut.EndOfStream) {
                $line = $stdOut.ReadLine()
                if ($line -ne $null) { $line | Out-File -FilePath $uvicornLog -Append -Encoding utf8 }
            }
            if (-not $stdErr.EndOfStream) {
                $eline = $stdErr.ReadLine()
                if ($eline -ne $null) { $eline | Out-File -FilePath $uvicornLog -Append -Encoding utf8 }
            }
        } catch {
            # ignore intermittent read errors
        }
        Start-Sleep -Milliseconds 200
    }

    $exit = $proc.ExitCode
    "$(Get-Date -Format o) - uvicorn exited (code=$exit). Restarting in 5s" | Out-File -FilePath $monitorLog -Append -Encoding utf8
    Start-Sleep -Seconds 5
}
