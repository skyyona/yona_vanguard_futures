# 백테스팅 백엔드를 지속 실행(모니터링)하는 스크립트
# 사용법: PowerShell에서 이 파일을 실행하거나 새 창으로 시작하세요.

$ErrorActionPreference = 'Stop'

# 프로젝트 루트
$root = Resolve-Path "$PSScriptRoot\.."
$root = $root.Path

# 가상환경 파이썬 실행 파일 경로
$python = Join-Path $root ".venv_backtest\Scripts\python.exe"

# 로그 디렉터리
$logDir = Join-Path $PSScriptRoot 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logFile = Join-Path $logDir 'uvicorn.log'

while ($true) {
    Write-Output "-------------------------------"
    Write-Output "Starting backtesting_backend at $(Get-Date -Format o)"
    Write-Output "Using python: $python"

    # Uvicorn 실행, stdout/stderr를 로그에 저장하면서 콘솔에도 출력
    & $python -m uvicorn backtesting_backend.app_main:app --host 127.0.0.1 --port 8001 --log-level info 2>&1 | Tee-Object -FilePath $logFile

    Write-Output "Process exited at $(Get-Date -Format o). Restarting in 5 seconds..."
    Start-Sleep -Seconds 5
}
