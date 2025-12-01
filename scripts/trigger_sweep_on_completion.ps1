param(
    [Parameter(Mandatory=$false)] [int]$StartingPid,
    [Parameter(Mandatory=$false)] [string]$Symbol = 'PIPPINUSDT',
    [Parameter(Mandatory=$false)] [string]$SlippageGrid = '0.0,0.0005,0.001',
    [Parameter(Mandatory=$false)] [int]$McIter = 50,
    [Parameter(Mandatory=$false)] [int]$Workers = 4,
    [Parameter(Mandatory=$false)] [int]$MaxCandidates = 5
)

Write-Output "Trigger monitor started. Waiting for current MC to finish..."

function Find-MCProcess {
    param()
    $p = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*mc_robustness.py*' } | Select-Object -First 1
    return $p
}

# use a writable local variable to avoid param name collisions in some shells
$targetPid = $StartingPid
if (-not $targetPid) {
    $p = Find-MCProcess
    if ($p) { $targetPid = $p.ProcessId }
}

if (-not $targetPid) {
    Write-Output "No MC process found; starting sweep immediately."
} else {
    while ($true) {
        $proc = Get-Process -Id $targetPid -ErrorAction SilentlyContinue
        if (-not $proc) { break }
        Start-Sleep -Seconds 30
    }
    Write-Output "Detected MC process $targetPid has exited. Starting slippage sweep."
}

$cwd = Get-Location
$extra = @('--max-candidates', $MaxCandidates.ToString(), '--slippage-grid', $SlippageGrid)
Write-Output "Starting background MC sweep via run_mc_background.ps1 (helper). Extra args: $($extra -join ' ')"
& .\scripts\run_mc_background.ps1 -Symbol $Symbol -Interval '5m' -Start $null -End $null -MCIter $McIter -Workers $Workers -ExtraArgs $extra

Write-Output "Slippage sweep started via helper; logs at results\${Symbol.ToLower()}_mc_bg_stdout.log and *_mc_bg_stderr.log"
