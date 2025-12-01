$start = [int64][double]((Get-Date).ToUniversalTime().AddDays(-7) - (Get-Date '1970-01-01')).TotalMilliseconds
$end = [int64][double]((Get-Date).ToUniversalTime() - (Get-Date '1970-01-01')).TotalMilliseconds
$body = @{ 
    strategy_name = 'auto_grid_test';
    symbol = 'BTCUSDT';
    interval = '1m';
    start_time = $start;
    end_time = $end;
    initial_balance = 1000.0;
    leverage = 1;
    parameters = @{ position_size = 0.1 };
    optimization_mode = $true;
    optimization_ranges = @{ fast_ema_period = @(5,9); slow_ema_period = @(21,34); stop_loss_pct = @(0.005,0.01) };
    fee_pct = 0.001;
    slippage_pct = 0.001
} | ConvertTo-Json -Depth 10

try {
    $resp = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/v1/backtest/run_backtest' -Method Post -ContentType 'application/json' -Body $body
    Write-Host 'POST RESPONSE:' ($resp | ConvertTo-Json -Depth 5)
} catch {
    Write-Host 'POST ERROR:' $_.Exception.Message
    exit 2
}

$run_id = $resp.run_id
Write-Host "Run ID: $run_id"
$status = ''
$startTime = Get-Date
while ($true) {
    Start-Sleep -Seconds 2
    try {
        $s = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/v1/backtest/backtest_status/$run_id" -Method Get
        $status = $s.status
        Write-Host ("Status: {0} Progress: {1}" -f $status, ($s.progress -as [string]))
        if ($status -eq 'completed' -or $status -eq 'failed') { break }
    } catch {
        Write-Host 'STATUS ERROR:' $_.Exception.Message
        break
    }
    if (((Get-Date) - $startTime).TotalSeconds -gt 300) { Write-Host 'Timeout waiting for run to complete'; break }
}

if ($status -eq 'completed') {
    try {
        $res = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/v1/backtest/backtest_result/$run_id" -Method Get
        Write-Host 'RESULT:' ($res | ConvertTo-Json -Depth 10)
    } catch {
        Write-Host 'RESULT FETCH ERROR:' $_.Exception.Message
    }
} else {
    Write-Host "Run did not complete. Final status: $status"
}
