try {
    [ScriptBlock]::Create((Get-Content '.\sanitize_retry_with_backoff.ps1' -Raw)) | Out-Null
    Write-Output 'PARSE_OK: sanitize_retry_with_backoff.ps1'
} catch {
    Write-Output ('PARSE_ERR: sanitize_retry_with_backoff.ps1 -> ' + $_.Exception.Message)
}

try {
    [ScriptBlock]::Create((Get-Content '.\tmp_kill_and_retry.ps1' -Raw)) | Out-Null
    Write-Output 'PARSE_OK: tmp_kill_and_retry.ps1'
} catch {
    Write-Output ('PARSE_ERR: tmp_kill_and_retry.ps1 -> ' + $_.Exception.Message)
}
