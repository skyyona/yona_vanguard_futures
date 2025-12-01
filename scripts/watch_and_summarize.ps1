param(
    [Parameter(Mandatory=$false)] [string]$Symbol = 'pippinusdt',
    [Parameter(Mandatory=$false)] [int]$PollSeconds = 30
)

$symbolLower = $Symbol.ToLower()
$csvPath = Join-Path -Path (Get-Location) -ChildPath "results\${symbolLower}_mc_robustness.csv"
$summaryPath = Join-Path -Path (Get-Location) -ChildPath "results\${symbolLower}_mc_robustness_summary.txt"
Write-Output "Watcher started for $csvPath (poll every $PollSeconds s). Will write summary to $summaryPath"

while ($true) {
    if (Test-Path $csvPath) {
        try {
            $rows = Import-Csv -Path $csvPath
            if (-not $rows) { Start-Sleep -Seconds $PollSeconds; continue }

            $lines = @()
            $lines += "MC Robustness Summary for $Symbol - Generated: $(Get-Date -Format o)"
            $lines += "Rows: $($rows.Count)"
            $lines += ""
            foreach ($r in $rows | Sort-Object {[int]$_.rank}) {
                $rank = $r.rank
                $stop = $r.stop_loss_pct
                $pos = $r.position_size
                $tp = $r.take_profit_pct
                $vf = $r.volume_spike_factor
                $mean = $r.mc_mean_profit_pct
                $std = $r.mc_std_profit_pct
                $p5 = $r.mc_5th_pct
                $neg = $r.mc_negative_pct
                $samples = $r.mc_samples
                $lines += "후보 순위 $rank: stop_loss=$stop, position_size=$pos, take_profit=$tp, volume_spike_factor=$vf"
                $lines += "  - 평균 수익률: $mean"
                $lines += "  - 표준편차: $std"
                $lines += "  - 5번째 백분위(하위 5%): $p5"
                $lines += "  - 손실 비중(%): $neg"
                $lines += "  - 샘플수: $samples"
                $lines += ""
            }

            $lines += "Note: 이 요약은 파일에 저장된 MC 집계값을 그대로 표기합니다. (mc-iter 수와 샘플수를 확인하세요)"
            $lines | Out-File -FilePath $summaryPath -Encoding utf8
            Write-Output "Summary written to $summaryPath"
            # also write a brief JSON-like summary for machine reading
            Exit 0
        } catch {
            Write-Error "Error reading CSV: $_"
            Start-Sleep -Seconds $PollSeconds
            continue
        }
    }
    Start-Sleep -Seconds $PollSeconds
}
