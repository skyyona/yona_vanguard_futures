$log = 'C:\Users\User\new\yona_vanguard_futures\post_reboot_verify_log.txt'
Write-Output "LOG-PATH: $log"
if (Test-Path $log) {
    $info = Get-Item $log
    Write-Output ("FileSizeBytes: {0}" -f $info.Length)
    Write-Output ("LastWriteTime: {0}" -f $info.LastWriteTime)
    $first = (Get-Content $log -TotalCount 1)[0]
    Write-Output ("FirstLine: {0}" -f $first)
    if ($first -match 'started: (.*) ===') {
        $start = [datetime]::Parse($matches[1])
        Write-Output ("ParsedStart: {0}" -f $start)
        Write-Output ("Elapsed: {0}" -f ((Get-Date)-$start))
    } else {
        Write-Output "No start timestamp parsed"
    }
    Write-Output "---- Last 200 lines ----"
    Get-Content $log -Tail 200 | ForEach-Object { Write-Output $_ }
} else {
    Write-Output "Log not found"
}

Write-Output '---Processes matching criteria---'
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'post_reboot_verify.ps1' -or $_.CommandLine -match 'pytest' -or $_.CommandLine -match '\bpy\b' -or $_.CommandLine -match 'docker' -or $_.CommandLine -match 'wsl') } | Select-Object ProcessId,Name,CommandLine | ForEach-Object { Write-Output ("PID: {0} Name: {1} Cmd: {2}" -f $_.ProcessId,$_.Name,$_.CommandLine) }
Write-Output '---Docker services---'
Get-Service -Name *docker* -ErrorAction SilentlyContinue | Select Name,Status | ForEach-Object { Write-Output ("{0}: {1}" -f $_.Name,$_.Status) }
Write-Output '---End'
