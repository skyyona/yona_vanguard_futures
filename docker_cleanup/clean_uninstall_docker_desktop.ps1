<#
clean_uninstall_docker_desktop.ps1
Usage: Run PowerShell as Administrator and run this script.
This script attempts to fully uninstall Docker Desktop and remove leftover files and WSL distros.
IT IS DESTRUCTIVE: it will remove Docker images, containers, volumes and configuration.
#>

function Ensure-Elevation {
    if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
        Write-Output "Not elevated. Re-launching elevated..."
        Start-Process -FilePath pwsh -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File \"$PSCommandPath\"" -Verb RunAs
        Exit
    }
}

Ensure-Elevation

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = "$env:TEMP\docker_backup_$timestamp.zip"
$pathsToBackup = @(
    "$env:APPDATA\Docker",
    "$env:LOCALAPPDATA\Docker",
    "$env:LOCALAPPDATA\DockerDesktop",
    "C:\ProgramData\DockerDesktop",
    "C:\ProgramData\Docker",
    "$env:ProgramFiles\Docker"
)

Write-Output "Backing up existing Docker folders (if present) to: $backup"
$existing = @()
foreach ($p in $pathsToBackup) {
    if (Test-Path $p) { $existing += $p }
}

if ($existing.Count -gt 0) {
    try {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $tempFolder = Join-Path $env:TEMP "docker_backup_$timestamp"
        New-Item -Path $tempFolder -ItemType Directory -Force | Out-Null
        foreach ($p in $existing) {
            $dest = Join-Path $tempFolder ([IO.Path]::GetFileName($p))
            Write-Output "Copying $p -> $dest"
            robocopy $p $dest /MIR /NFL /NDL /NJH /NJS | Out-Null
        }
        [IO.Compression.ZipFile]::CreateFromDirectory($tempFolder, $backup)
        Remove-Item -Path $tempFolder -Recurse -Force
        Write-Output "Backup created: $backup"
    } catch {
        Write-Warning "Backup failed: $_"
    }
} else {
    Write-Output "No Docker config folders found to backup."
}

# Stop Docker services and processes
Write-Output "Stopping Docker services and processes..."
Try { Stop-Service -Name com.docker.service -ErrorAction SilentlyContinue -WarningAction SilentlyContinue } Catch {}
Get-Process -Name 'Docker Desktop','Docker','dockerd','com.docker.service' -ErrorAction SilentlyContinue | ForEach-Object { 
    try { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue } catch {}
}

# Attempt uninstall using winget if available
if (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Output "Attempting uninstall with winget..."
    try {
        winget uninstall --id Docker.DockerDesktop -e --silent
    } catch {
        Write-Warning "winget uninstall failed or interactive uninstall required: $_"
    }
} else {
    Write-Output "winget not found. Will attempt to locate uninstall string in registry."
}

# If the app still present in ARP, attempt to uninstall via UninstallString
function Uninstall-From-ARP {
    $keys = @("HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
              "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
              "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall")
    foreach ($k in $keys) {
        Get-ChildItem -Path $k -ErrorAction SilentlyContinue | ForEach-Object {
            $dn = (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).DisplayName
            if ($dn -and $dn -like "*Docker*") {
                $un = (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).UninstallString
                if ($un) {
                    Write-Output "Found uninstall for: $dn"
                    Write-Output "Uninstall string: $un"
                    # Clean the command if it is wrapped with quotes and /I or /X
                    $cmd = $un
                    # Run uninstall (may require UI)
                    try {
                        Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $cmd -Wait -NoNewWindow
                        Write-Output "Launched uninstall for $dn"
                    } catch {
                        Write-Warning "Failed to launch uninstall: $_"
                    }
                }
            }
        }
    }
}

Uninstall-From-ARP

# Give the system a moment
Start-Sleep -Seconds 5

# Shutdown WSL then unregister docker-managed distros (destructive)
Write-Output "Shutting down WSL and unregistering docker-managed distros (this removes docker images/containers)"
try { wsl --shutdown } catch {}
try { wsl --unregister docker-desktop } catch {}
try { wsl --unregister docker-desktop-data } catch {}

# Remove leftover folders (best-effort)
$leftovers = @(
    "$env:APPDATA\Docker",
    "$env:LOCALAPPDATA\Docker",
    "$env:LOCALAPPDATA\DockerDesktop",
    "C:\ProgramData\DockerDesktop",
    "C:\ProgramData\Docker",
    "$env:ProgramFiles\Docker",
    "$env:ProgramFiles\Docker\Docker",
    "$env:ProgramFiles\Docker Desktop",
    "$env:ProgramFiles\Docker Inc",
    "$env:ProgramFiles(x86)\Docker"
)
foreach ($p in $leftovers) {
    if (Test-Path $p) {
        try {
            Write-Output "Removing $p"
            Remove-Item -Path $p -Recurse -Force -ErrorAction SilentlyContinue
        } catch {
            Write-Warning ("Could not remove {0}: {1}" -f $p, $_)
        }
    }
}

# Optional: remove registry keys (uncomment only if you want registry cleaned)
<#
Write-Output "Cleaning Docker-related registry keys (optional; commented out by default)"
$regPaths = @("HKCU:\Software\Docker","HKLM:\SOFTWARE\Docker Inc.")
foreach ($r in $regPaths) {
    if (Test-Path $r) {
        try { Remove-Item -Path $r -Recurse -Force -ErrorAction SilentlyContinue; Write-Output "Removed $r" } catch { Write-Warning "Failed to remove $r: $_" }
    }
}
#>

Write-Output "Cleanup finished. It is recommended to reboot the machine now."
Write-Output "Backup (if created): $backup"
Write-Output "After reboot, follow reinstall instructions in the repository README or run the commands listed in the instructions document."

Exit 0
