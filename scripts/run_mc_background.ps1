param(
    [string]$Symbol = 'PIPPINUSDT',
    [string]$Interval = '5m',
    [string]$Start = '2025-11-18',
    [string]$End = '2025-11-24',
    [int]$MCIter = 100,
    [int]$Workers = 4,
    [string[]]$ExtraArgs = @()
)

# PowerShell helper to launch mc_robustness.py in background with redirected logs.
# Uses full Python executable to avoid virtualenv/path issues.

$python = 'C:/Users/User/AppData/Local/Programs/Python/Python313/python.exe'
$script = Join-Path -Path (Split-Path -Parent $MyInvocation.MyCommand.Definition) -ChildPath 'mc_robustness.py'
$cwd = Convert-Path (Join-Path -Path $PSScriptRoot -ChildPath '..')

$out_dir = Join-Path $cwd 'results'
if (-not (Test-Path $out_dir)) { New-Item -ItemType Directory -Path $out_dir | Out-Null }

$stdout = Join-Path $out_dir "$($Symbol.ToLower())_mc_bg_stdout.log"
$stderr = Join-Path $out_dir "$($Symbol.ToLower())_mc_bg_stderr.log"

# Build argument array: script path first, then script args
$argList = @($script, '--symbol', $Symbol, '--interval', $Interval)
if ($Start -and $Start -ne '') { $argList += @('--start', $Start) }
if ($End -and $End -ne '') { $argList += @('--end', $End) }
$argList += @('--mc-iter', $MCIter.ToString(), '--workers', $Workers.ToString())

Write-Output "Launching MC robustness background job for $Symbol"
Write-Output "Python: $python"
Write-Output "Script: $script"
Write-Output "Cwd: $cwd"
Write-Output "Stdout -> $stdout"
Write-Output "Stderr -> $stderr"

# append any extra args provided
if ($ExtraArgs -and $ExtraArgs.Count -gt 0) {
    $argList += $ExtraArgs
}

# remove any null/empty args which break Start-Process
$argList = $argList | Where-Object { $_ -ne $null -and $_ -ne '' }

# Start process detached and return immediately
$proc = Start-Process -FilePath $python -ArgumentList $argList -WorkingDirectory $cwd -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru

Write-Output "Started process Id: $($proc.Id)"
Write-Output "Use 'Get-Process -Id $($proc.Id)' to inspect or 'Wait-Process -Id $($proc.Id)' to wait." 

return 0
