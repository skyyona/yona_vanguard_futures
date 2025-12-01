Set-StrictMode -Off
$cwd = (Resolve-Path .).Path
Set-Location $cwd
if (-not (Test-Path results)) { New-Item -ItemType Directory results | Out-Null }

$arglist = @(
    'scripts\mc_robustness.py',
    '--symbol','PIPPINUSDT',
    '--interval','5m',
    '--start','2025-11-18',
    '--end','2025-11-24',
    '--mc-iter','10',
    '--workers','1'
)

Write-Output "Starting local MC job: python $($arglist -join ' ')"
$proc = Start-Process -FilePath 'python' -ArgumentList $arglist -RedirectStandardOutput 'results\mc_ci_stdout.log' -RedirectStandardError 'results\mc_ci_stderr.log' -PassThru
Write-Output "Started background process PID=$($proc.Id)"
Start-Sleep -Seconds 6

if (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue) {
    Write-Output "Process PID $($proc.Id) still running"
} else {
    Write-Output "Process PID $($proc.Id) not running (likely completed)"
}

Write-Output '--- STDOUT (head) ---'
Get-Content -Path results\mc_ci_stdout.log -ErrorAction SilentlyContinue | Select-Object -First 200 | ForEach-Object { Write-Output $_ }
Write-Output '--- STDERR (head) ---'
Get-Content -Path results\mc_ci_stderr.log -ErrorAction SilentlyContinue | Select-Object -First 200 | ForEach-Object { Write-Output $_ }

Write-Output 'Local MC run finished.'
