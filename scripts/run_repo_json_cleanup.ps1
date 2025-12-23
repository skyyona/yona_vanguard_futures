Param(
    [string]$RepoRoot = (Get-Location).Path,
    [int]$Days = 7,
    [string[]]$ExcludePatterns = @('\.git','\.venv','\\venv','\\env','node_modules','site-packages','__pycache__','vss_tmp'),
    [switch]$Perform
)

$cutoff = (Get-Date).AddDays(-$Days)

$all = Get-ChildItem -Path $RepoRoot -Include *.json -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
    $ok = $true
    foreach ($pat in $ExcludePatterns) { if ($_.FullName -match $pat) { $ok = $false; break } }
    $ok
}

Write-Output "Total JSON files found in repo: $($all.Count)"

$recent = $all | Where-Object { $_.LastWriteTime -ge $cutoff }
Write-Output "Recent (<= $Days days): $($recent.Count)"
if ($recent.Count -gt 0) { $recent | Select-Object FullName, LastWriteTime | Format-Table -AutoSize }

$old = $all | Where-Object { $_.LastWriteTime -lt $cutoff }
Write-Output "Older (>$Days days): $($old.Count)"
if ($old.Count -gt 0) { $old | Select-Object FullName, LastWriteTime | Format-Table -AutoSize }

if ($Perform) {
    $dump = Join-Path -Path $RepoRoot -ChildPath "outputs\legacy\repo_dump"
    $archive = Join-Path -Path $RepoRoot -ChildPath "outputs\legacy\repo_archive"
    New-Item -ItemType Directory -Path $dump -Force | Out-Null
    New-Item -ItemType Directory -Path $archive -Force | Out-Null

    $moveLog = Join-Path $dump ("moves_repo_$(Get-Date -Format 'yyyyMMdd_HHmmss').log")

    foreach ($f in $recent) {
        try {
            $rel = $f.FullName.Substring($RepoRoot.Length).TrimStart('\')
            $dest = Join-Path $dump $rel
            New-Item -ItemType Directory -Path (Split-Path $dest) -Force | Out-Null
            Move-Item -LiteralPath $f.FullName -Destination $dest -Force
            "MOVED: $($f.FullName) -> $dest" | Out-File -FilePath $moveLog -Append -Encoding utf8
        } catch {
            "FAILED MOVE: $($f.FullName) | $_" | Out-File -FilePath $moveLog -Append -Encoding utf8
        }
    }

    if ($old.Count -gt 0) {
        $zip = Join-Path $archive ("archive_repo_{0:yyyyMMdd_HHmmss}.zip" -f (Get-Date))
        $oldPaths = $old | ForEach-Object { $_.FullName }
        Compress-Archive -Path $oldPaths -DestinationPath $zip -Force
        foreach ($f in $old) { Remove-Item -LiteralPath $f.FullName -Force }
        Write-Output "Archived $($old.Count) files to $zip"
    } else {
        Write-Output "No old files to archive."
    }

    Write-Output "Performed repo moves and archives. Move log: $moveLog"
} else {
    Write-Output "Dry-run only. To perform, re-run with -Perform."
}
