Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
$repo = Resolve-Path -Path '..' | Select-Object -ExpandProperty Path
# ensure working directory is repository root so relative script paths resolve correctly
Set-Location $repo
$rb = Get-ChildItem -Path (Join-Path $repo 'results_backups') -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1
if (-not $rb) {
  Write-Output 'NO_BACKUP_FOUND' ; exit 2
}
$backup = $rb.FullName
Write-Output ("USING_BACKUP={0}" -f $backup)
$out = Join-Path $repo 'results\sanitize_inplace_run_out.txt'
$err = Join-Path $repo 'results\sanitize_inplace_run_err.txt'
$py = 'python'
# use repository-root-relative path to the sanitizer script
$sanitizer = Join-Path $repo 'scripts\sanitize_results.py'
$args = @($sanitizer,'--results-dir','results','--inplace','--backup-dir',$backup)
Write-Output ('RUN: ' + $py + ' ' + ($args -join ' '))
Start-Process -FilePath $py -ArgumentList $args -NoNewWindow -Wait -RedirectStandardOutput $out -RedirectStandardError $err
Write-Output 'SANITIZER_EXITED'