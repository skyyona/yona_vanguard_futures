<#
clean_uninstall_docker_desktop_nobackup.ps1
Usage: Run PowerShell as Administrator and run this script.
This version SKIPS backups and directly stops/removes Docker Desktop components.
IT IS DESTRUCTIVE: it will remove Docker images, containers, volumes and configuration.
#>

function Ensure-Elevation {
    if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
        Write-Output "Not elevated. Re-launching elevated..."
        Start-Process -FilePath powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File \"$PSCommandPath\"" -Verb RunAs
        Exit
    }
}

Ensure-Elevation

Write-Output "[1] WARNING: Running WITHOUT backup. Docker data will be lost."

# Stop Docker services and processes
Write-Output "[2] Stopping Docker services and processes..."
Try { Stop-Service -Name com.docker.service -ErrorAction SilentlyContinue -WarningAction SilentlyContinue } Catch {}
Get-Process -Name 'Docker Desktop','Docker','dockerd','com.docker.service','com.docker.backend' -ErrorAction SilentlyContinue | ForEach-Object {
    try { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue } catch {}
}

# Attempt uninstall via ARP registry entries (if any remain)
Write-Output "[3] Attempting uninstall from registry (Apps & Features entries)..."
function Uninstall-From-ARP {
    $keys = @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall"
    )
    foreach ($k in $keys) {
        Get-ChildItem -Path $k -ErrorAction SilentlyContinue | ForEach-Object {
            $p = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
            $dn = $p.DisplayName
            if ($dn -and $dn -like "*Docker*") {
                $un = $p.UninstallString
                Write-Output "  Found uninstall entry: $dn"
                if ($un) {
                    Write-Output "  Uninstall string: $un"
                    try {
                        Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $un -Wait -NoNewWindow -ErrorAction SilentlyContinue
                        Write-Output "  Launched uninstall for $dn (may have shown GUI)."
                    } catch {
                        Write-Warning ("  Failed to launch uninstall for {0}: {1}" -f $dn, $_)
                    }
                }
            }
        }
    }
}

Uninstall-From-ARP

Start-Sleep -Seconds 3

# Shutdown WSL then unregister docker-managed distros (destructive)
Write-Output "[4] Shutting down WSL and unregistering docker-managed distros (this removes docker images/containers)."
try { wsl --shutdown } catch {}
try { wsl --unregister docker-desktop } catch {}
try { wsl --unregister docker-desktop-data } catch {}

# Remove leftover folders (best-effort, no backup)
Write-Output "[5] Removing leftover Docker folders (no backup)..."
$leftovers = @(
    "$env:APPDATA\Docker",
    "$env:LOCALAPPDATA\Docker",
    "$env:LOCALAPPDATA\DockerDesktop",
    "C:\\ProgramData\\DockerDesktop",
    "C:\\ProgramData\\Docker",
    "$env:ProgramFiles\Docker",
    "$env:ProgramFiles\Docker\\Docker",
    "$env:ProgramFiles\Docker Desktop",
    "$env:ProgramFiles\Docker Inc",
    "$env:ProgramFiles(x86)\Docker"
)
foreach ($p in $leftovers) {
    if (Test-Path $p) {
        Write-Output "  Removing $p ..."
        try {
            Remove-Item -Path $p -Recurse -Force -ErrorAction SilentlyContinue
        } catch {
            Write-Warning ("  Could not remove {0}: {1}" -f $p, $_)
        }
    }
}

Write-Output "[6] Done. A reboot is strongly recommended before reinstalling Docker Desktop."
Exit 0
