Param(
    [string]$UserRoot = 'C:\Users\User',
    [string]$RepoPath = 'C:\Users\User\new',
    [int]$Days = 7,
    [switch]$Perform
)

$cutoff = (Get-Date).AddDays(-$Days)

$all = Get-ChildItem -Path $UserRoot -Include *.json -Recurse -File -ErrorAction SilentlyContinue | Where-Object { -not ($_.FullName -like "$RepoPath*") }

Write-Output "Total JSON files found (excluding repo): $($all.Count)"

$recent = $all | Where-Object { $_.LastWriteTime -ge $cutoff }
Write-Output "Recent (<= $Days days): $($recent.Count)"
if ($recent.Count -gt 0) { $recent | Select-Object FullName, LastWriteTime | Format-Table -AutoSize }

$old = $all | Where-Object { $_.LastWriteTime -lt $cutoff }
Write-Output "Older (>$Days days): $($old.Count)"
if ($old.Count -gt 0) { $old | Select-Object FullName, LastWriteTime | Format-Table -AutoSize }

if ($Perform) {
    $target = Join-Path -Path $RepoPath -ChildPath "outputs\legacy\user_dump"
    $archive = Join-Path -Path $RepoPath -ChildPath "outputs\legacy\user_archive"
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    New-Item -ItemType Directory -Path $archive -Force | Out-Null

    $log = Join-Path $target ("moves_$(Get-Date -Format 'yyyyMMdd_HHmmss').log")

    foreach ($f in $recent) {
        try {
            $rel = $f.FullName.Substring($UserRoot.Length).TrimStart('\')
            $dest = Join-Path $target $rel
            New-Item -ItemType Directory -Path (Split-Path $dest) -Force | Out-Null
            Move-Item -LiteralPath $f.FullName -Destination $dest -Force
            "MOVED: $($f.FullName) -> $dest" | Out-File -FilePath $log -Append -Encoding utf8
        } catch {
            "FAILED MOVE: $($f.FullName) | $_" | Out-File -FilePath $log -Append -Encoding utf8
        }
    }

    if ($old.Count -gt 0) {
        $zip = Join-Path $archive ("archive_{0:yyyyMMdd_HHmmss}.zip" -f (Get-Date))
        $oldPaths = $old | ForEach-Object { $_.FullName }
        Compress-Archive -Path $oldPaths -DestinationPath $zip -Force
        foreach ($f in $old) { Remove-Item -LiteralPath $f.FullName -Force }
        Write-Output "Archived $($old.Count) files to $zip"
    } else {
        Write-Output "No old files to archive."
    }

    Write-Output "Performed moves and archives. Move log: $log"
} else {
    Write-Output "Dry-run only. To perform moves and archives, re-run with -Perform."
}
