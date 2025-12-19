<#
docker_install_and_verify.ps1
Automates: ensure WSL update finishes, download Docker Desktop (stable amd64), run installer elevated, and verify installation.
Run this script as Administrator.
This script does NOT remove existing Docker installations by default. To perform a clean uninstall first, run the clean_uninstall_docker_desktop.ps1 script.
#>

function Ensure-Elevation {
    if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
        Write-Output "Not elevated. Re-launching elevated..."
        Start-Process -FilePath powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File \"$PSCommandPath\"" -Verb RunAs
        Exit
    }
}

Ensure-Elevation

# Parameters
$installerUrl = 'https://desktop.docker.com/win/stable/amd64/Docker%20Desktop%20Installer.exe'
$outExe = Join-Path $env:USERPROFILE 'Downloads\DockerDesktopInstaller.exe'
$timeoutMinutes = 15

Write-Output "Docker Desktop installer target: $outExe"

# 1) Ensure any ongoing WSL update completes
Write-Output "Running 'wsl --update' to ensure kernel is up-to-date and waiting for completion (this may take a few minutes)..."
try {
    wsl --update
} catch {
    Write-Warning "wsl --update returned an error or is unsupported on this system: $_"
}

# If wsl --update started background activity, wait a short time
Start-Sleep -Seconds 3

# Poll `wsl --status` for the presence of any 'Installing' progress line for up to 5 minutes
$pollTimeout = (Get-Date).AddMinutes(5)
while ((Get-Date) -lt $pollTimeout) {
    try {
        $status = wsl --status 2>&1 | Out-String
    } catch {
        $status = $_.ToString()
    }
    if ($status -match "Install|Installing|installation|updating|Updating|0.0%|%") {
        Write-Output "WSL status indicates activity; waiting 5s and rechecking..."
        Start-Sleep -Seconds 5
        continue
    }
    break
}

Write-Output "WSL update step complete or no active update detected."

# 2) Download installer
Write-Output "Downloading Docker Desktop installer from: $installerUrl"
try {
    # Use Invoke-WebRequest; fallback to bits transfer if failed
    Invoke-WebRequest -Uri $installerUrl -OutFile $outExe -UseBasicParsing -ErrorAction Stop
} catch {
    Write-Warning "Invoke-WebRequest failed: $_. Trying Start-BitsTransfer..."
    try {
        Start-BitsTransfer -Source $installerUrl -Destination $outExe -ErrorAction Stop
    } catch {
        Write-Error "Failed to download installer via Invoke-WebRequest and BitsTransfer: $_"
        Exit 2
    }
}

if (-not (Test-Path $outExe)) {
    Write-Error "Installer file was not created at $outExe"
    Exit 3
}

# 3) Compute SHA256 hash and show file version if possible
try {
    $hash = Get-FileHash -Path $outExe -Algorithm SHA256
    Write-Output "Downloaded installer SHA256: $($hash.Hash)"
} catch {
    Write-Warning "Could not compute file hash: $_"
}
try {
    $vi = (Get-Item $outExe).VersionInfo
    Write-Output "Installer FileVersion: $($vi.FileVersion) ProductVersion: $($vi.ProductVersion)"
} catch {
    # ignore
}

# 4) Launch installer elevated and wait for exit
Write-Output "Launching installer elevated. Please accept UAC and complete the installer GUI. The script will wait for installer to exit."
try {
    $p = Start-Process -FilePath $outExe -Verb RunAs -PassThru
    Write-Output "Installer PID: $($p.Id)"
    Write-Output "Waiting for installer to exit (this may take some minutes)..."
    $p.WaitForExit()
    Write-Output "Installer exited with code: $($p.ExitCode)"
} catch {
    Write-Error "Failed to launch installer elevated: $_"
    Exit 4
}

# 5) Wait for Docker daemon to start (poll docker info)
$startTime = Get-Date
$endTime = $startTime.AddMinutes($timeoutMinutes)
$dockerReady = $false
Write-Output "Polling 'docker info' for up to $timeoutMinutes minutes to detect daemon readiness..."
while ((Get-Date) -lt $endTime) {
    try {
        $info = docker info 2>&1 | Out-String
        if ($info -and $info -notmatch "cannot" -and $info -match "Server Version|Containers|Images") {
            Write-Output "Docker daemon is responding."
            $dockerReady = $true
            break
        }
        Write-Output "docker info not ready yet. Retrying in 5s..."
    } catch {
        Write-Output "docker info error: $_. Retrying in 5s..."
    }
    Start-Sleep -Seconds 5
}

if (-not $dockerReady) {
    Write-Warning "Docker daemon did not become ready within timeout. Collecting basic diagnostics..."
}

# 6) Post-install checks (WSL status, installed distributions, service state)
Write-Output "---- Post-install verification ----"
try { wsl --status } catch { Write-Warning "wsl --status failed: $_" }
try { wsl -l -v } catch { Write-Warning "wsl -l -v failed: $_" }
try { Get-Service -Name com.docker.service -ErrorAction SilentlyContinue | Format-List Name,Status } catch {}
try { docker version } catch { Write-Warning "docker version failed: $_" }
try { docker info } catch { Write-Warning "docker info failed: $_" }

# 7) Show important log locations for troubleshooting
Write-Output "If Docker failed to start, check these logs:"
Write-Output "- %LOCALAPPDATA%\Docker\log\host\docker-desktop.exe.log"
Write-Output "- C:\ProgramData\DockerDesktop\service.txt"
Write-Output "- WSL status and 'wsl -l -v' output"

Write-Output "Script completed. If Docker did not start correctly, attach the above logs and outputs for further analysis."
Exit 0
