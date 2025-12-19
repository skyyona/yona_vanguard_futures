<#
fix_wsl_update_install_msi.ps1
Attempts to recover from a stuck `wsl --update` by:
 - stopping msiexec if hung
 - shutting down WSL
 - downloading official WSL2 kernel MSI
 - installing MSI with verbose logging
 - verifying WSL status and setting default version 2

IMPORTANT: Run this script as Administrator. It will stop installer processes and perform installations.
#>

function Ensure-Elevation {
    if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
        Write-Output "Not elevated. Re-launching elevated..."
        Start-Process -FilePath powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File \"$PSCommandPath\"" -Verb RunAs
        Exit
    }
}

Ensure-Elevation

$msiUrl = 'https://wslstorestorage.blob.core.windows.net/wslblob/wsl_update_x64.msi'
$msiPath = Join-Path $env:TEMP 'wsl_update_x64.msi'
$logPath = Join-Path $env:TEMP 'wsl_msi_install.log'

Write-Output "[1] Checking for running Windows Installer (msiexec) processes..."
$msiProcs = Get-Process -Name msiexec -ErrorAction SilentlyContinue
if ($msiProcs) {
    Write-Output "Found msiexec processes (will attempt to stop them):"
    $msiProcs | Format-Table Id,ProcessName,StartTime -AutoSize
    try {
        $msiProcs | ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 2
        Write-Output "Stopped msiexec processes."
    } catch {
        Write-Warning "Could not stop msiexec processes: $_"
    }
} else {
    Write-Output "No msiexec processes found."
}

Write-Output "[2] Shutting down WSL (safe)"
try { wsl --shutdown; Start-Sleep -Seconds 2 } catch { Write-Warning "wsl --shutdown failed or not present: $_" }

Write-Output "[3] Downloading WSL2 kernel MSI to: $msiPath"
try {
    if (Test-Path $msiPath) { Remove-Item $msiPath -Force -ErrorAction SilentlyContinue }
    Invoke-WebRequest -Uri $msiUrl -OutFile $msiPath -UseBasicParsing -ErrorAction Stop
    Write-Output "Download complete."
} catch {
    Write-Error "Failed to download MSI: $_"; Exit 10
}

if (-not (Test-Path $msiPath)) {
    Write-Error "MSI not found after download. Exiting."
    Exit 11
}

Write-Output "[4] Installing MSI with verbose logging to: $logPath"
try {
    # Ensure previous log removed
    if (Test-Path $logPath) { Remove-Item $logPath -Force -ErrorAction SilentlyContinue }
    $args = '/i', "`"$msiPath`"", '/l*v', "`"$logPath`""
    $proc = Start-Process -FilePath msiexec.exe -ArgumentList $args -Wait -PassThru -ErrorAction Stop
    Write-Output "msiexec exit code: $($proc.ExitCode)"
} catch {
    Write-Error "MSI installation failed: $_"; Exit 12
}

Write-Output "[5] Post-install: wsl --status"
try { wsl --status } catch { Write-Warning "wsl --status failed: $_" }

Write-Output "[6] Ensure WSL default version 2"
try {
    wsl --set-default-version 2
} catch {
    Write-Warning "Failed to set default version to 2: $_"
}

Write-Output "[7] Show distributions (if any)"
try { wsl -l -v } catch { Write-Warning "wsl -l -v failed: $_" }

Write-Output "[8] If WSL still not healthy, collect logs and show installer log path: $logPath"
if (Test-Path $logPath) {
    Write-Output "MSI install log (last 200 lines):"
    Get-Content -Path $logPath -Tail 200 -ErrorAction SilentlyContinue
} else {
    Write-Warning "No MSI log found at $logPath"
}

Write-Output "Script completed. If issues remain, please copy the output above and the MSI log ($logPath) and share them for further analysis."
Exit 0
