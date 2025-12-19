$out = 'C:\Users\User\new\yona_vanguard_futures\A1_diagnostics.txt'
function Log($m){ (Get-Date).ToString('o') + ' ' + $m | Out-File -FilePath $out -Append -Encoding utf8 }
Set-Content -Path $out -Value "=== WSL Failure Diagnostics started: $(Get-Date -Format o) ===`n" -Encoding utf8

Log '1) Basic system info'
try { Log ("OS: " + (Get-CimInstance Win32_OperatingSystem).Caption + " " + (Get-CimInstance Win32_OperatingSystem).Version) } catch { Log ('OS info failed: ' + $_.Exception.Message) }
try { Log ("COMPUTER: " + $env:COMPUTERNAME + ' User: ' + $env:USERNAME) } catch {}
try { $drive = Get-PSDrive C; Log ("C drive Free: " + ($drive.Free/1GB) + " GB; Used: " + (($drive.Used)/1GB + " GB")) } catch {}

Log '2) AppInstaller package info'
try { Get-AppxPackage -Name *AppInstaller* | Select Name,PackageFullName | ForEach-Object { Log ("Appx: " + $_.Name + ' | ' + $_.PackageFullName) } } catch { Log ('Get-AppxPackage failed: ' + $_.Exception.Message) }

Log '3) Check temp directories and permissions'
try { $tmp = "$env:TEMP"; Log ("User TEMP: $tmp"); $fi = Get-Item $tmp; Log ("TEMP exists: " + (Test-Path $tmp)); $acl = (Get-Acl $tmp).Access | ForEach-Object { $_.IdentityReference.ToString() + ':' + $_.FileSystemRights }; $acl -join ',' | Out-Null; Log ("TEMP ACL sample: " + ((Get-Acl $tmp).Owner)) } catch { Log ('Temp check failed: ' + $_.Exception.Message) }
try { $localtmp = "$env:LOCALAPPDATA\Temp"; Log ("LocalAppData Temp exists: " + (Test-Path $localtmp)) } catch {}

Log '4) Recent Event Log entries (last 24 hours) - key providers'
$since = (Get-Date).AddHours(-24)
$providers = @('Microsoft-Windows-AppxPackaging','Microsoft-Windows-AppxInstallation','Microsoft-Windows-AppxDeployment/Operational','Microsoft-Windows-WindowsUpdateClient','Microsoft-Windows-Servicing','Microsoft-Windows-AppModel-Runtime')
foreach ($p in $providers) {
    try {
        Log ("-- Provider: $p --")
        # try logname or provider
        $events = @()
        try { $events = Get-WinEvent -FilterHashtable @{ProviderName=$p; StartTime=$since} -ErrorAction SilentlyContinue } catch { }
        if (-not $events -or $events.Count -eq 0) {
            try { $events = Get-WinEvent -FilterHashtable @{LogName=$p; StartTime=$since} -ErrorAction SilentlyContinue } catch { }
        }
        if ($events -and $events.Count -gt 0) {
            $events | Where-Object { $_.LevelDisplayName -in @('Error','Warning') } | Select-Object TimeCreated, ProviderName, Id, LevelDisplayName, @{Name='Message';Expression={$_.Message.Substring(0,[Math]::Min(1000,$_.Message.Length))}} | ForEach-Object { Log ("EV: {0} | {1} | Id:{2} | {3} | {4}" -f $_.TimeCreated.ToString('o'), $_.ProviderName, $_.Id, $_.LevelDisplayName, $_.Message) }
        } else { Log ("No events found for provider/log $p") }
    } catch { Log ("Event collection for $p failed: " + $_.Exception.Message) }
}

Log '5) General System/WindowsUpdate recent errors (System/Application last 24h)'
try {
    Get-WinEvent -FilterHashtable @{LogName='System'; StartTime=$since} -ErrorAction SilentlyContinue | Where-Object { $_.LevelDisplayName -eq 'Error' -and ($_.Message -match 'WSL' -or $_.Message -match 'Windows Subsystem' -or $_.Message -match 'Appx' -or $_.ProviderName -match 'WindowsUpdate') } | Select-Object TimeCreated, ProviderName, Id, LevelDisplayName, @{Name='Message';Expression={$_.Message.Substring(0,[Math]::Min(1000,$_.Message.Length))}} | ForEach-Object { Log ("SYSERR: {0} | {1} | Id:{2} | {3} | {4}" -f $_.TimeCreated.ToString('o'), $_.ProviderName, $_.Id, $_.LevelDisplayName, $_.Message) }
} catch { Log ('System event scan failed: ' + $_.Exception.Message) }

Log '6) Tail CBS.log and DISM log (errors/warnings)'
try { if (Test-Path 'C:\Windows\Logs\CBS\CBS.log') { Get-Content 'C:\Windows\Logs\CBS\CBS.log' -Tail 500 | ForEach-Object { if ($_ -match 'error|failed|fail|exception|HRESULT' -or $_ -ne '') { Log ('CBS: ' + $_) } } } else { Log 'CBS.log not found' } } catch { Log ('CBS tail failed: ' + $_.Exception.Message) }
try { if (Test-Path 'C:\Windows\Logs\DISM\dism.log') { Get-Content 'C:\Windows\Logs\DISM\dism.log' -Tail 200 | ForEach-Object { Log ('DISM: ' + $_) } } else { Log 'dism.log not found' } } catch { Log ('DISM tail failed: ' + $_.Exception.Message) }

Log '7) WSL status and installed components'
try { wsl --status 2>&1 | ForEach-Object { Log ('WSLSTAT: ' + $_) } } catch { Log ('wsl --status failed: ' + $_.Exception.Message) }
try { wsl --list --verbose 2>&1 | ForEach-Object { Log ('WSLLIST: ' + $_) } } catch { }

Log '8) AppInstaller or msixinstaller error logs via EventLog'
try { Get-WinEvent -FilterHashtable @{ProviderName='Microsoft-Windows-AppxDeploymentServer'; StartTime=$since} -ErrorAction SilentlyContinue | Select TimeCreated, Id, LevelDisplayName, @{Name='Message';Expression={$_.Message.Substring(0,[Math]::Min(1000,$_.Message.Length))}} | ForEach-Object { Log ('APPSRV: ' + $_.TimeCreated.ToString('o') + ' | ' + $_.Id + ' | ' + $_.LevelDisplayName + ' | ' + $_.Message) } } catch { Log ('AppxDeploymentServer query failed: ' + $_.Exception.Message) }

Log '=== WSL Failure Diagnostics end ==='
Write-Output ('Diagnostics written to: ' + $out)
