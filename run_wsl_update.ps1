$out = 'C:\Users\User\wsl_web_update_output.txt'
Write-Output ('Running wsl --update --web-download, logging to ' + $out)

try {
    wsl --update --web-download 2>&1 | Tee-Object -FilePath $out
    Write-Output ('ExitCode: ' + $LASTEXITCODE)
} catch {
    Write-Output ('wsl --update failed exception: ' + $_.Exception.Message)
}

if (Test-Path $out) {
    Write-Output '--- Output Log (Tail 200) ---'
    Get-Content $out -Tail 200
} else {
    Write-Output 'Output file not created'
}

Write-Output '--- Command Finished ---'