$log = "C:\Users\User\new\yona_vanguard_futures\wu_fix_run_now_log.txt"
function Log($s){ "$((Get-Date).ToString('s')) - $s" | Out-File -FilePath $log -Append }
Start-Transcript -Path $log -Append -Force

Log "=== WU Fix RunNow Started ==="

# Ensure running as admin
$IsAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Log "IsAdmin: $IsAdmin"
if(-not $IsAdmin){ Write-Error "Script must be run as Administrator"; exit 1 }

# Create restore point
try{ Checkpoint-Computer -Description "pre-wu-fix-runnow" -RestorePointType "MODIFY_SETTINGS"; Log "Restore point created" } catch { Log "Restore point failed: $_" }

# SFC
Log "Running sfc /scannow"
try { sfc /scannow *>&1 | Out-File -FilePath $log -Append } catch { Log "sfc failed: $_" }

# DISM restore
Log "Running DISM /Online /Cleanup-Image /RestoreHealth"
try { DISM /Online /Cleanup-Image /RestoreHealth *>&1 | Out-File -FilePath $log -Append } catch { Log "DISM failed: $_" }

# Stop services
Log "Stopping update services"
net stop wuauserv 2>&1 | Out-File -FilePath $log -Append
net stop cryptSvc 2>&1 | Out-File -FilePath $log -Append
net stop bits 2>&1 | Out-File -FilePath $log -Append
net stop msiserver 2>&1 | Out-File -FilePath $log -Append

# Rename folders (use fallback to move)
$sd = "C:\Windows\SoftwareDistribution"
$sdold = "C:\Windows\SoftwareDistribution.old"
if(Test-Path $sd){
    try{ Rename-Item -Path $sd -NewName "SoftwareDistribution.old" -Force; Log "Renamed SoftwareDistribution" } catch { Log "Rename failed, attempting Move-Item: $_"; try { Move-Item -Path $sd -Destination $sdold -Force; Log "Moved SoftwareDistribution" } catch { Log "Move failed: $_" } }
} else { Log "SoftwareDistribution not found" }

$cat = "C:\Windows\System32\catroot2"
$catold = "C:\Windows\System32\catroot2.old"
if(Test-Path $cat){
    try{ Rename-Item -Path $cat -NewName "catroot2.old" -Force; Log "Renamed catroot2" } catch { Log "Rename catroot2 failed: $_" }
} else { Log "catroot2 not found" }

# Start services
Log "Starting update services"
net start wuauserv 2>&1 | Out-File -FilePath $log -Append
net start cryptSvc 2>&1 | Out-File -FilePath $log -Append
net start bits 2>&1 | Out-File -FilePath $log -Append
net start msiserver 2>&1 | Out-File -FilePath $log -Append

# WSL update
Log "Attempting wsl --update"
try{ wsl --update *>&1 | Out-File -FilePath $log -Append; wsl --shutdown *>&1 | Out-File -FilePath $log -Append } catch { Log "WSL update error: $_" }

# Docker info
Log "Collecting docker info"
try{ docker info *>&1 | Out-File -FilePath $log -Append } catch { Log "Docker info failed: $_" }

Log "=== WU Fix RunNow Finished ==="
Stop-Transcript
Start-Process notepad.exe $log
