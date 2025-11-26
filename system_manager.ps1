Param()

# system_manager.ps1 - Robust launcher for Live, Backtesting, and GUI
Set-StrictMode -Version Latest
$BaseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $BaseDir 'logs'
If (-not (Test-Path $LogDir)) { New-Item -Path $LogDir -ItemType Directory | Out-Null }
$SMLog = Join-Path $LogDir 'system_manager_launch.log'

"------------------------------" | Out-File -FilePath $SMLog -Encoding utf8
"Launch at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File -FilePath $SMLog -Append -Encoding utf8
"BASE_DIR=$BaseDir" | Out-File -FilePath $SMLog -Append -Encoding utf8

function Wait-Port {
    param(
        [int]$Port,
        [int]$TimeoutSec = 20
    )
    $start = Get-Date
    Add-Content -Path $SMLog -Value "Waiting for port $Port up to $TimeoutSec seconds..."
    while ((Get-Date) -lt $start.AddSeconds($TimeoutSec)) {
        try {
            $res = Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -WarningAction SilentlyContinue
            if ($res -and $res.TcpTestSucceeded) {
                Add-Content -Path $SMLog -Value "Port $Port is now listening."
                return $true
            }
        } catch {
            # ignore
        }
        Start-Sleep -Seconds 1
    }
    Add-Content -Path $SMLog -Value "Timeout waiting for port $Port."
    return $false
}

function Start-ServiceProcess {
    param(
        [string]$Name,
        [string]$Cmd,
        [int]$Port
    )
    Add-Content -Path $SMLog -Value ("Starting {0}: {1}" -f $Name, $Cmd)
    # Launch via cmd so redirection works consistently and working dir is BaseDir
    $fullCmd = "cd /d `"$BaseDir`" && $Cmd"
    Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', $fullCmd -WindowStyle Normal
    # Wait for port
    $ok = Wait-Port -Port $Port -TimeoutSec 20
    Add-Content -Path $SMLog -Value "$Name port $Port ready: $ok"
    return $ok
}

# paths
$live_py = Join-Path $BaseDir '.venv_new\Scripts\python.exe'
$back_py = Join-Path $BaseDir '.venv_backtest\Scripts\python.exe'

If (-not (Test-Path (Join-Path $BaseDir 'backend\logs'))) { New-Item -Path (Join-Path $BaseDir 'backend\logs') -ItemType Directory | Out-Null }
If (-not (Test-Path (Join-Path $BaseDir 'backtesting_backend\logs'))) { New-Item -Path (Join-Path $BaseDir 'backtesting_backend\logs') -ItemType Directory | Out-Null }

# Start Live backend
$livePort = 8000
If ((Test-NetConnection -ComputerName 127.0.0.1 -Port $livePort -WarningAction SilentlyContinue).TcpTestSucceeded) {
    Add-Content -Path $SMLog -Value "Port $livePort appears in use; skipping Live start."
} else {
    $liveCmd = "`"$live_py`" -m uvicorn backend.app_main:app --host 0.0.0.0 --port $livePort --log-level info > `"$BaseDir\backend\logs\uvicorn_$livePort.log`" 2>&1"
    Start-ServiceProcess -Name 'Live Backend' -Cmd $liveCmd -Port $livePort | Out-Null
}

# Quick health-check for Live
try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$livePort/docs" -TimeoutSec 5 -ErrorAction Stop
    Add-Content -Path $SMLog -Value "LIVE_DOCS:$($r.StatusCode)"
} catch {
    Add-Content -Path $SMLog -Value "LIVE_DOCS_ERROR:$($_.Exception.Message)"
}

# Start Backtesting backend
$backPort = 8001
If ((Test-NetConnection -ComputerName 127.0.0.1 -Port $backPort -WarningAction SilentlyContinue).TcpTestSucceeded) {
    Add-Content -Path $SMLog -Value "Port $backPort appears in use; skipping Backtesting start."
} else {
    $backCmd = "`"$back_py`" -m uvicorn backtesting_backend.app_main:app --host 0.0.0.0 --port $backPort --log-level info > `"$BaseDir\backtesting_backend\logs\uvicorn_$backPort.log`" 2>&1"
    Start-ServiceProcess -Name 'Backtesting Backend' -Cmd $backCmd -Port $backPort | Out-Null
}

# Quick health-check for Backtesting
try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$backPort/docs" -TimeoutSec 5 -ErrorAction Stop
    Add-Content -Path $SMLog -Value "BACK_DOCS:$($r.StatusCode)"
} catch {
    Add-Content -Path $SMLog -Value "BACK_DOCS_ERROR:$($_.Exception.Message)"
}

# Optionally start GUI if present
If (Test-Path (Join-Path $BaseDir 'gui\main.py')) {
    If (Test-Path $live_py) { $gui_py = $live_py } else { $gui_py = 'python' }
    $guiCmd = "`"$gui_py`" ""$BaseDir\gui\main.py"" > `"$BaseDir\gui\logs\gui.log`" 2>&1"
    If (-not (Test-Path (Join-Path $BaseDir 'gui\logs'))) { New-Item -Path (Join-Path $BaseDir 'gui\logs') -ItemType Directory | Out-Null }
    Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', "cd /d `"$BaseDir\gui`" && $guiCmd" -WindowStyle Normal
    Add-Content -Path $SMLog -Value "Started GUI (if available)"
} else {
    Add-Content -Path $SMLog -Value "GUI not found; skipping."
}

Add-Content -Path $SMLog -Value "All done. See per-service logs for details."
Write-Output "Launcher finished; see $SMLog for details."
