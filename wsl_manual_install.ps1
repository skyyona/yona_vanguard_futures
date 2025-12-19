<#
wsl_manual_install.ps1

Purpose: Run as Administrator to manually install the WSL2 kernel MSI,
enable necessary Windows features (WSL and VirtualMachinePlatform),
and capture logs for troubleshooting.

Usage: Right-click and 'Run with PowerShell' as Administrator, or this
script will re-launch itself elevated when executed by a non-admin user.
#>

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Log {
    param([string]$Message)
    $t = (Get-Date).ToString('s')
    $line = "$t`t$Message"
    Add-Content -Path $global:LogFile -Value $line -Encoding UTF8
}

# Log paths
$global:LogFile = Join-Path $env:TEMP 'wsl_manual_install.log'
$global:MsiLog = Join-Path $env:TEMP 'wsl_msi_install.log'

if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] 'Administrator')) {
    Write-Output "Not running as Administrator — re-launching elevated..."
    Start-Process -FilePath powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit 0
}

# Running as admin from here
Write-Log "=== Started wsl_manual_install.ps1 (elevated) ==="
Write-Log "User: $env:USERNAME; Machine: $env:COMPUTERNAME"

try {
    # Ensure TLS 1.2 for downloads
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

    Write-Log "Enabling required Windows features (WSL, VirtualMachinePlatform) via DISM..."
    $dismCmds = @(
        '/Online /Enable-Feature /FeatureName:Microsoft-Windows-Subsystem-Linux /All /NoRestart',
        '/Online /Enable-Feature /FeatureName:VirtualMachinePlatform /All /NoRestart'
    )
    foreach ($arg in $dismCmds) {
        Write-Log "Running: dism.exe $arg"
        $out = & dism.exe $arg 2>&1
        Write-Log ("DISM output: " + ($out -join "`n"))
    }

    # Download the official WSL kernel MSI (official Microsoft URL)
    $msiUrl = 'https://wslstorestorage.blob.core.windows.net/wslblob/wsl_update_x64.msi'
    $dest = Join-Path $env:TEMP 'wsl_update_x64.msi'
    Write-Log "Downloading WSL kernel MSI from $msiUrl to $dest"
    if (Test-Path $dest) { Remove-Item -Force -ErrorAction SilentlyContinue $dest }
    Invoke-WebRequest -Uri $msiUrl -OutFile $dest -UseBasicParsing
    Write-Log "Downloaded MSI size: $( (Get-Item $dest).Length ) bytes"

    # Install MSI silently and capture verbose MSI log
    Write-Log "Starting MSI install (msiexec). MSI log at $global:MsiLog"
    $msiArgs = "/i `"$dest`" /qn /l*v `"$global:MsiLog`""
    $p = Start-Process -FilePath msiexec.exe -ArgumentList $msiArgs -Wait -PassThru
    $exit = $p.ExitCode
    Write-Log "msiexec exit code: $exit"

    if ($exit -ne 0) {
        Write-Log "MSI install returned non-zero exit code. See $global:MsiLog for details."
        throw "MSI install failed with exit code $exit"
    }

    # Run `wsl --update` and `wsl --status` and capture outputs
    Write-Log "Running 'wsl --update'"
    try {
        $updateOut = & wsl.exe --update 2>&1
        Write-Log ("wsl --update output: " + ($updateOut -join "`n"))
    } catch {
        Write-Log ("wsl --update failed: " + $_.Exception.Message)
    }

    Write-Log "Running 'wsl --status'"
    try {
        $statusOut = & wsl.exe --status 2>&1
        Write-Log ("wsl --status output: " + ($statusOut -join "`n"))
    } catch {
        Write-Log ("wsl --status failed: " + $_.Exception.Message)
    }

    # Try starting Docker service if present
    Write-Log "Attempting to start Docker service 'com.docker.service' (if present)"
    try {
        if (Get-Service -Name 'com.docker.service' -ErrorAction SilentlyContinue) {
            Start-Service -Name 'com.docker.service' -ErrorAction Stop
            Write-Log "Started com.docker.service"
        } else {
            Write-Log "com.docker.service not found; Docker Desktop may not be installed or uses a different service name."
        }
    } catch {
        Write-Log ("Start-Service(com.docker.service) failed: " + $_.Exception.Message)
    }

    Write-Log "Checking Docker daemon via 'docker info'"
    try {
        $dockerInfo = & docker info 2>&1
        Write-Log ("docker info output: " + ($dockerInfo -join "`n"))
    } catch {
        Write-Log ("docker info failed: " + $_.Exception.Message)
    }

    Write-Log "Completed installation steps successfully."
    Write-Log "Please review $global:LogFile and $global:MsiLog for detailed logs."
    Write-Output "Logs: $global:LogFile and $global:MsiLog"
}
catch {
    Write-Log "ERROR: $($_.Exception.Message)"
    Write-Log "Exception details: $($_ | Out-String)"
    Write-Output "An error occurred. Check $global:LogFile and $global:MsiLog for details."
    exit 1
}

exit 0
