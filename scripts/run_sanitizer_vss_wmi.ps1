<#
WMI-based VSS fallback script.
Creates a VSS snapshot via Win32_ShadowCopy.Create, copies the `results` folder from the snapshot to a temp dir,
runs the sanitizer against the copied tree (inplace with backup), then deletes the shadow.
Requires: Administrator privileges.
Usage (run from repo root in elevated PowerShell):
  .\scripts\run_sanitizer_vss_wmi.ps1
#>

param(
    [string]$ResultsDir = 'results',
    [string]$BackupRoot = 'results_backups',
    [string]$Python = 'python',
    [string]$TempRoot = '.\vss_tmp'
)

function Write-Log { param($m) Write-Host "[VSS-WMI] $m" }

# check admin
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "This script must be run as Administrator."; exit 2
}

# Resolve repo root and results path
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptRoot '..')
Set-Location $repoRoot
$resultsFull = (Resolve-Path $ResultsDir).Path
Write-Log "Results full path: $resultsFull"

# derive drive letter and relative path
$driveQualifier = Split-Path -Path $resultsFull -Qualifier
$driveLetter = $driveQualifier.TrimEnd('\')
$relPath = $resultsFull.Substring($driveQualifier.Length)
Write-Log "Source drive: $driveLetter"
Write-Log "Relative path: $relPath"

$ts = (Get-Date).ToString('yyyyMMddTHHmmssZ')
$workDir = Join-Path $TempRoot $ts
New-Item -ItemType Directory -Path $workDir -Force | Out-Null
Write-Log "Workdir: $workDir"

# Create shadow via WMI
try {
    $wmiClass = [wmiclass]"\\.\root\cimv2:Win32_ShadowCopy"
    Write-Log "Requesting shadow Create($driveLetter\) ..."
    $res = $wmiClass.Create("$driveLetter\", "ClientAccessible")
    if ($res.ReturnValue -ne 0) {
        Write-Error "Win32_ShadowCopy.Create returned $($res.ReturnValue). See permissions & VSS service."; exit 4
    }
    $shadowId = $res.ShadowID
    Write-Log "Created shadow ID: $shadowId"
} catch {
    Write-Error "Failed creating shadow: $_"; exit 5
}

# find shadow object
$shadowObj = Get-WmiObject -Class Win32_ShadowCopy -Filter "ID='$shadowId'"
if (-not $shadowObj) { Write-Error "Shadow object not found after create."; exit 6 }
$deviceObject = $shadowObj.DeviceObject
Write-Log "DeviceObject: $deviceObject"

# Build source path inside shadow and dest
# deviceObject often looks like: \\?\GLOBALROOT\Device\HarddiskVolumeShadowCopyX\
$sourceSnapshotPath = Join-Path $deviceObject $relPath
Write-Log "Snapshot source path: $sourceSnapshotPath"

$dest = Join-Path (Resolve-Path $workDir).Path 'results_copy'
New-Item -ItemType Directory -Path $dest -Force | Out-Null
Write-Log "Destination copy: $dest"

# Use robocopy to copy from snapshot path to dest; write output to file
$robOut = Join-Path $workDir 'robocopy_out.txt'
$robCmd = "robocopy `"$sourceSnapshotPath`" `"$dest`" /MIR /COPYALL /R:2 /W:5"
Write-Log "Running: $robCmd"
cmd.exe /c $robCmd 2>&1 | Out-File -FilePath $robOut -Encoding utf8
Write-Log "Robocopy finished; output: $robOut"

# Run sanitizer against the copied results
$sanitizeOut = Join-Path $workDir 'sanitize_out.txt'
$backupDir = Join-Path $BackupRoot ("vss_backup_$ts")
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Write-Log "Running sanitizer against copy (results_dir=$dest)"
# Call python directly; capture stdout/stderr
& $Python scripts\sanitize_results.py --results-dir $dest --inplace --backup-dir $backupDir 2>&1 | Out-File -FilePath $sanitizeOut -Encoding utf8
Write-Log "Sanitizer finished; output: $sanitizeOut"

# Cleanup: delete the shadow
try {
    Write-Log "Deleting shadow $shadowId"
    $del = $shadowObj.Delete()
    Write-Log "Shadow delete returned: $del"
} catch {
    Write-Warning "Failed to delete shadow: $_"
}

Write-Log "VSS-WMI run complete. Workdir: $workDir"
Write-Host "Workdir: $workDir"
exit 0
