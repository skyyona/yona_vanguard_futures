# Run both services detached via cmd so Explorer double-click / CI can start them
# Uses absolute python paths from venvs and writes per-service logs.

$base = 'C:\Users\User\new\yona_vanguard_futures'
$live_py = Join-Path $base '.venv_new\Scripts\python.exe'
$back_py = Join-Path $base '.venv_backtest\Scripts\python.exe'

$live_work = Join-Path $base 'backend'
$back_work = Join-Path $base 'backtesting_backend'

$live_log = Join-Path $base 'backend\logs\uvicorn_8000.log'
$back_log = Join-Path $base 'backtesting_backend\logs\uvicorn_8001.log'

if (-not (Test-Path $live_py)) { Write-Output "Live python not found: $live_py" }
if (-not (Test-Path $back_py)) { Write-Output "Backtest python not found: $back_py" }

$live_cmd = "cd /d `"$live_work`" && `"$live_py`" -m uvicorn app_main:app --host 0.0.0.0 --port 8000 --log-level info > `"$live_log`" 2>&1"
$back_cmd = "cd /d `"$back_work`" && `"$back_py`" -m uvicorn backtesting_backend.app_main:app --host 0.0.0.0 --port 8001 --log-level info > `"$back_log`" 2>&1"

Write-Output "Starting Live: $live_cmd"
Start-Process -FilePath cmd.exe -ArgumentList '/c', $live_cmd -WindowStyle Minimized

Start-Sleep -Milliseconds 250

Write-Output "Starting Backtest: $back_cmd"
Start-Process -FilePath cmd.exe -ArgumentList '/c', $back_cmd -WindowStyle Minimized

Write-Output 'Started services; waiting 3s to check /docs'
Start-Sleep -Seconds 3

$urls = @('http://127.0.0.1:8000/docs','http://127.0.0.1:8001/docs')
foreach ($u in $urls) {
    try {
        $r = Invoke-WebRequest -UseBasicParsing -Uri $u -TimeoutSec 5
        Write-Output "$u STATUS $($r.StatusCode)"
    } catch {
        Write-Output "$u ERROR $_"
    }
}
