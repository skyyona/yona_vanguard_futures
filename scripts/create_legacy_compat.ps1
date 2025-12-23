Param(
    [string]$Root = "C:\Users\User\new",
    [switch]$Apply,
    [switch]$MoveContents
)

# mappings: legacy -> outputs subfolder
$mappings = @{
    'backtest_results_mtf' = 'outputs\\backtests_mtf'
    'backtest_results' = 'outputs\\backtests'
    'backtest_results_extended' = 'outputs\\backtests_extended'
}

function Write-Action { param($s) Write-Output $s }

foreach ($legacy in $mappings.Keys) {
    $legacyPath = Join-Path $Root $legacy
    $targetRel = $mappings[$legacy]
    $targetPath = Join-Path $Root $targetRel

    Write-Action "\n=== Processing mapping: $legacy -> $targetRel ==="

    if (-not (Test-Path $targetPath)) {
        Write-Action "Target does not exist: $targetPath"
        if ($Apply) {
            New-Item -ItemType Directory -Path $targetPath -Force | Out-Null
            Write-Action "Created target: $targetPath"
        } else {
            Write-Action "(dry-run) Would create: $targetPath"
        }
    } else {
        Write-Action "Target exists: $targetPath"
    }

    if (-not (Test-Path $legacyPath)) {
        Write-Action "Legacy path not present: $legacyPath"
        if ($Apply) {
            # create junction from legacy -> target
            try {
                if (Test-Path $legacyPath) { Remove-Item -Path $legacyPath -Recurse -Force }
                cmd /c mklink /J "$legacyPath" "$targetPath" | Out-Null
                Write-Action "Created junction: $legacyPath -> $targetPath"
            } catch {
                Write-Action "Failed to create junction: $_"
            }
        } else {
            Write-Action "(dry-run) Would create junction: $legacyPath -> $targetPath"
        }
        continue
    }

    # legacy exists and is directory
    $items = Get-ChildItem -Path $legacyPath -Force -ErrorAction SilentlyContinue
    if ($items.Count -eq 0) {
        Write-Action "Legacy directory exists but empty: $legacyPath"
        if ($Apply) {
            try {
                Remove-Item -Path $legacyPath -Recurse -Force
                cmd /c mklink /J "$legacyPath" "$targetPath" | Out-Null
                Write-Action "Replaced empty legacy dir with junction to target"
            } catch {
                Write-Action "Failed to replace legacy dir: $_"
            }
        } else {
            Write-Action "(dry-run) Would remove empty dir and create junction"
        }
        continue
    }

    # legacy has content
    Write-Action "Legacy dir has $($items.Count) entries: $legacyPath"
    if (-not $Apply) {
        Write-Action "(dry-run) Would move contents to $targetPath and create junction, or skip if MoveContents not set"
        continue
    }

    if ($MoveContents) {
        try {
            # ensure target
            New-Item -ItemType Directory -Path $targetPath -Force | Out-Null
            foreach ($it in $items) {
                $dest = Join-Path $targetPath $it.Name
                Move-Item -LiteralPath $it.FullName -Destination $dest -Force
            }
            Write-Action "Moved contents from $legacyPath to $targetPath"
            # remove legacy and create junction
            Remove-Item -Path $legacyPath -Recurse -Force
            cmd /c mklink /J "$legacyPath" "$targetPath" | Out-Null
            Write-Action "Created junction after moving contents"
        } catch {
            Write-Action "Error during move/create junction: $_"
        }
    } else {
        Write-Action "Legacy dir contains files. To move contents and create junction, re-run with -Apply -MoveContents"
    }
}

Write-Output "\nDone. Note: creating junctions requires appropriate privileges and behavior may vary on older Windows builds."
