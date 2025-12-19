# run_wsl_update_utf8.ps1
# Ensures console uses UTF-8, runs WSL web-download update, logs output.
chcp 65001 > $null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$out = 'C:\Users\User\wsl_web_update_output_utf8.txt'
Write-Output ('Running wsl --update --web-download (UTF-8) and logging to ' + $out)

try {
    wsl --update --web-download 2>&1 | Tee-Object -FilePath $out
    Write-Output ('ExitCode: ' + $LASTEXITCODE)
} catch {
    Write-Output ('wsl --update failed exception: ' + $_.Exception.Message)
}

if (Test-Path $out) {
    Write-Output '--- Output Log (Tail 200) ---'
    Get-Content $out -Tail 200 | ForEach-Object { Write-Output $_ }
} else {
    Write-Output 'Output file not created'
}

Write-Output '--- Command Finished ---'
