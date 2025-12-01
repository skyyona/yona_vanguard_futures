<#
PowerShell helper: create a VSS snapshot, copy the `results` folder from the snapshot, run sanitizer against the copy, and clean up.
Requires: Administrator privileges (to run diskshadow and expose snapshots).
Usage: run from repository root in an elevated PowerShell session.
#>
param(
    [string]$ResultsDir = 'results',
    [string]$BackupRoot = 'results_backups',
    [string]$Python = 'python',
    [string]$TempRoot = '.\vss_tmp',
    [switch]$DryRun = $false
)

function Write-Log { param($m) Write-Host "[VSS] $m" }

# Resolve paths
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
# Move to repository root (parent of scripts)
$repoRoot = Resolve-Path (Join-Path $scriptRoot '..')
Set-Location $repoRoot
if (-not (Test-Path $ResultsDir)) {
    Write-Error "Results directory '$ResultsDir' not found under repository root: $repoRoot"; exit 2
}
$resultsFull = (Resolve-Path $ResultsDir).Path
Write-Log "Results full path: $resultsFull"

# Determine drive letter for snapshot source
# Use the PSDrive root for robust drive-root resolution (handles different path formats)
$volumeRoot = (Get-Item $resultsFull).PSDrive.Root  # e.g. 'C:\'
$driveLetter = $volumeRoot.TrimEnd('\')
Write-Log "Source drive: $driveLetter"

# Choose an available drive letter to expose the snapshot
$letters = 'X','Y','Z'
$exposeDrive = $null
foreach ($l in $letters) {
    if (-not (Get-PSDrive -Name $l -ErrorAction SilentlyContinue)) { $exposeDrive = $l; break }
}
if (-not $exposeDrive) { Write-Error 'No free drive letter available (X,Y,Z).'; exit 3 }
Write-Log ("Will attempt to expose snapshot as drive '{0}:'" -f $exposeDrive)

# Prepare temp workspace
$ts = (Get-Date).ToString('yyyyMMddTHHmmssZ')
$workDir = Join-Path $TempRoot $ts
New-Item -ItemType Directory -Path $workDir -Force | Out-Null
$diskshadowScript = Join-Path $workDir 'diskshadow_create.txt'
$diskshadowDelete = Join-Path $workDir 'diskshadow_delete.txt'

# If requested, perform a non-destructive dry-run that validates paths and python invocation only
if ($DryRun) {
    Write-Log "DRY RUN: workdir=$workDir"
    Write-Log ("Results full path: {0}" -f $resultsFull)
    Write-Log ("Source drive: {0}" -f $driveLetter)
    # compute relative path for dry-run display (will be validated later)
    $relPathPreview = $resultsFull.Substring($volumeRoot.Length).TrimStart('\','/')
    Write-Log ("Relative path inside volume: {0}" -f $relPathPreview)
    Write-Log ("Selected expose drive: {0}" -f $exposeDrive)
    try {
        $pyv = & $Python '--version' 2>&1
        Write-Log ("Python invocation OK: {0}" -f ($pyv -join ' '))
    } catch {
        Write-Log ("Python invocation failed: $_")
    }
    Write-Log "DRY RUN complete — skipping snapshot and copy steps."
    exit 0
}

# Use a unique alias
$alias = "snap_$ts"
# compute the relative path inside the volume (used for joining with the exposed drive)
$relPath = $resultsFull.Substring($volumeRoot.Length)
# Ensure the relative path inside the volume does not start with a leading separator
$relPath = $relPath.TrimStart('\','/')

$dsContent = @(
    'SET CONTEXT PERSISTENT NOWRITERS',
    ("ADD VOLUME {0} ALIAS {1}" -f $driveLetter, $alias),
    'CREATE',
    ("EXPOSE %{0}% {1}:" -f $alias, $exposeDrive)
)

# Write diskshadow create script
$dsContent | Out-File -FilePath $diskshadowScript -Encoding ascii
Write-Log ("Wrote diskshadow script: {0}" -f $diskshadowScript)

# Run diskshadow create
$diskshadowCmd = Get-Command diskshadow.exe -ErrorAction SilentlyContinue
if (-not $diskshadowCmd) {
    Write-Error "diskshadow.exe not found in PATH. diskshadow (built-in Windows utility) is required to create VSS snapshots. Run this script in an elevated/admin session and ensure diskshadow is available."; exit 6
}
Write-Log "Running diskshadow to create and expose snapshot (requires admin)..."
$dsOut = & diskshadow.exe /s $diskshadowScript 2>&1
$dsOut | Out-File -FilePath (Join-Path $workDir 'diskshadow_create_out.txt') -Encoding utf8
Write-Log "diskshadow output written to diskshadow_create_out.txt"

# Verify exposed path
# Exposed root like 'X:\'
$exposedRoot = $exposeDrive + ':\'
Start-Sleep -Seconds 1
if (-not (Test-Path $exposedRoot)) {
    Write-Error "Snapshot was not exposed at $exposedRoot. Check diskshadow output: $workDir\diskshadow_create_out.txt"; exit 4
}

$sourceSnapshotPath = Join-Path $exposedRoot $relPath
if (-not (Test-Path $sourceSnapshotPath)) {
    Write-Error "Source path inside snapshot not found: $sourceSnapshotPath"; exit 5
}
Write-Log ("Snapshot source path: {0}" -f $sourceSnapshotPath)

# Copy snapshot results to a local temp folder using robocopy
$dest = Join-Path (Resolve-Path $workDir).Path 'results_copy'
New-Item -ItemType Directory -Path $dest -Force | Out-Null
Write-Log "Starting robocopy from snapshot to $dest"
# Use /MIR to mirror, /COPY:DAT to copy data/attributes/timestamps (avoids some permission issues). Limit retries to 2.
$robocopyCmd = "robocopy `"$sourceSnapshotPath`" `"$dest`" /MIR /COPY:DAT /R:2 /W:5"
Write-Log $robocopyCmd
# Run via cmd and capture output (robocopy returns special exit codes; we record output for debugging)
$rob = & cmd.exe /c $robocopyCmd 2>&1
$rob | Out-File -FilePath (Join-Path $workDir 'robocopy_out.txt') -Encoding utf8
# Optionally check robocopy exit codes by inspecting last exit code
if ($LASTEXITCODE -ge 8) {
    Write-Error "robocopy failed with exit code $LASTEXITCODE. See $workDir\robocopy_out.txt"; exit 7
}
Write-Log "Robocopy finished; output at $workDir\robocopy_out.txt"

# Run sanitizer against the copied results
$backupDir = Join-Path $BackupRoot ("vss_backup_$ts")
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Write-Log "Running sanitizer via python executable: $Python"
# Call the python executable directly with argument array to avoid embedding PowerShell-only flags
try {
    $sanitizeOut = & $Python 'scripts\sanitize_results.py' '--results-dir' $dest '--inplace' '--backup-dir' $backupDir 2>&1
} catch {
    $sanitizeOut = "Failed to invoke python ($Python): $_"
}
$sanitizeOut | Out-File -FilePath (Join-Path $workDir 'sanitize_out.txt') -Encoding utf8
Write-Log "Sanitizer run complete; output at $workDir\sanitize_out.txt"

# Clean up: delete created shadow(s)
$dsDelContent = @("SET CONTEXT PERSISTENT NOWRITERS","DELETE SHADOWS ALL")
$dsDelContent | Out-File -FilePath $diskshadowDelete -Encoding ascii
$dsDelOut = & diskshadow.exe /s $diskshadowDelete 2>&1
$dsDelOut | Out-File -FilePath (Join-Path $workDir 'diskshadow_delete_out.txt') -Encoding utf8
Write-Log "Requested shadow deletion; output at $workDir\diskshadow_delete_out.txt"

Write-Log "VSS-based sanitizer run completed. Workdir: $workDir"
Write-Host "STDOUT: $workDir\sanitize_out.txt"
Write-Host "Diskshadow logs: $workDir\diskshadow_create_out.txt, $workDir\diskshadow_delete_out.txt"

exit 0
