$log = "C:\Users\User\new\yona_vanguard_futures\wu_fix_log.txt"
function Log($s){ "$((Get-Date).ToString('s')) - $s" | Out-File -FilePath $log -Append }

Log "=== WU Fix Script Started ==="

# Check admin
$IsAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Log "IsAdmin: $IsAdmin"
if(-not $IsAdmin){ Write-Host "This script must be run as Administrator."; Log "Exiting: not admin"; exit 1 }

# Try creating restore point (best-effort)
try{
    Checkpoint-Computer -Description "pre-wu-fix" -RestorePointType "MODIFY_SETTINGS"
    Log "Restore point created"
}catch{
    Log "Restore point creation failed: $_"
}

# 1) SFC
Log "Starting sfc /scannow"
sfc /scannow 2>&1 | Out-File -FilePath $log -Append

# 2) DISM
Log "DISM /Online /Cleanup-Image /CheckHealth"
DISM /Online /Cleanup-Image /CheckHealth 2>&1 | Out-File -FilePath $log -Append
Log "DISM /Online /Cleanup-Image /ScanHealth"
DISM /Online /Cleanup-Image /ScanHealth 2>&1 | Out-File -FilePath $log -Append
Log "DISM /Online /Cleanup-Image /RestoreHealth"
DISM /Online /Cleanup-Image /RestoreHealth 2>&1 | Out-File -FilePath $log -Append

# 3) Stop Windows Update related services
Log "Stopping Windows Update related services"
net stop wuauserv 2>&1 | Out-File -FilePath $log -Append
net stop cryptSvc 2>&1 | Out-File -FilePath $log -Append
net stop bits 2>&1 | Out-File -FilePath $log -Append
net stop msiserver 2>&1 | Out-File -FilePath $log -Append

# 4) Rename SoftwareDistribution and catroot2 as backups
try{
    if(Test-Path "C:\Windows\SoftwareDistribution"){
        Log "Renaming SoftwareDistribution to SoftwareDistribution.old"
        Rename-Item -Path "C:\Windows\SoftwareDistribution" -NewName "SoftwareDistribution.old" -Force
    } else { Log "SoftwareDistribution not found" }
}catch{ Log "Error renaming SoftwareDistribution: $_" }

try{
    if(Test-Path "C:\Windows\System32\catroot2"){
        Log "Renaming catroot2 to catroot2.old"
        Rename-Item -Path "C:\Windows\System32\catroot2" -NewName "catroot2.old" -Force
    } else { Log "catroot2 not found" }
}catch{ Log "Error renaming catroot2: $_" }

# 5) Start services back
Log "Starting Windows Update related services"
net start wuauserv 2>&1 | Out-File -FilePath $log -Append
net start cryptSvc 2>&1 | Out-File -FilePath $log -Append
net start bits 2>&1 | Out-File -FilePath $log -Append
net start msiserver 2>&1 | Out-File -FilePath $log -Append

# 6) WSL update
Log "Attempting wsl --update"
try{
    wsl --update 2>&1 | Out-File -FilePath $log -Append
    wsl --shutdown 2>&1 | Out-File -FilePath $log -Append
}catch{ Log "WSL update error: $_" }

# 7) Final diagnostic
Log "Collecting final docker info"
try{ docker info 2>&1 | Out-File -FilePath $log -Append } catch { Log "Docker info failed: $_" }

Log "=== WU Fix Script Finished ==="
Start-Process notepad.exe $log
