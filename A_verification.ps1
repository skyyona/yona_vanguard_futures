$log = 'C:\Users\User\new\yona_vanguard_futures\A_verification_log.txt'
function Log($m){ (Get-Date).ToString('o') + ' ' + $m | Out-File -FilePath $log -Append -Encoding utf8 }
Log '=== A verification start ==='

# Check folders
Log ("catroot2 exists: {0}" -f (Test-Path 'C:\Windows\System32\catroot2'))
Log ("catroot2.old exists: {0}" -f (Test-Path 'C:\Windows\System32\catroot2.old'))
Log ("SoftwareDistribution exists: {0}" -f (Test-Path 'C:\Windows\SoftwareDistribution'))
Log ("SoftwareDistribution.old exists: {0}" -f (Test-Path 'C:\Windows\SoftwareDistribution.old'))

# Services
try { $svc = Get-Service -Name TrustedInstaller -ErrorAction Stop; Log ("TrustedInstaller: {0}" -f $svc.Status) } catch { Log 'TrustedInstaller: NotFound' }
try { $svc2 = Get-Service -Name wuauserv -ErrorAction Stop; Log ("wuauserv: {0}" -f $svc2.Status) } catch { Log 'wuauserv: NotFound' }
try { $svc3 = Get-Service -Name bits -ErrorAction Stop; Log ("bits: {0}" -f $svc3.Status) } catch { Log 'bits: NotFound' }
try { $svc4 = Get-Service -Name cryptSvc -ErrorAction Stop; Log ("cryptSvc: {0}" -f $svc4.Status) } catch { Log 'cryptSvc: NotFound' }

# Pending reboot / pending.xml
Log ("RebootRequired registry present: {0}" -f (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'))
Log ("WinSxS pending.xml present: {0}" -f (Test-Path "$env:windir\WinSxS\pending.xml"))

# Run wsl --update (capture output)
Log 'Running: wsl --update'
try { wsl --update 2>&1 | ForEach-Object { Log ("WSL: {0}" -f $_) }; Log ("wsl exitcode: {0}" -f $LASTEXITCODE) } catch { Log ("wsl failed exception: {0}" -f $_.Exception.Message) }

# Collect recent event log entries related to WSL/WindowsUpdate (last 6 hours)
Log 'Collecting event log entries (System, last 6 hours)'
try {
    $events = Get-WinEvent -FilterHashtable @{LogName='System'; StartTime=(Get-Date).AddHours(-6)} -ErrorAction SilentlyContinue | Where-Object { $_.Message -match 'Windows Subsystem for Linux|WSL|WindowsSubsystem' -or $_.ProviderName -match 'WindowsUpdate|Microsoft-Windows-WindowsUpdateClient' }
    if ($events) {
        $events | Select-Object TimeCreated, ProviderName, Id, LevelDisplayName, @{Name='Message';Expression={$_.Message.Substring(0,[Math]::Min(800,$_.Message.Length))}} | ForEach-Object { Log ("EV: {0} | {1} | Id:{2} | {3} | {4}" -f $_.TimeCreated.ToString('o'), $_.ProviderName, $_.Id, $_.LevelDisplayName, $_.Message) }
    } else { Log 'No matching system events found (last 6h)' }
} catch { Log ("Event log collection failed: {0}" -f $_.Exception.Message) }

# Tail CBS
Log 'Tail of CBS.log (last 200 lines)'
try {
    if (Test-Path 'C:\Windows\Logs\CBS\CBS.log') { Get-Content 'C:\Windows\Logs\CBS\CBS.log' -Tail 200 | ForEach-Object { Log ("CBS: {0}" -f $_) } } else { Log 'CBS.log not found' }
} catch { Log ("CBS read failed: {0}" -f $_.Exception.Message) }

Log '=== A verification end ==='
Write-Output ('A verification log written to: ' + $log)
