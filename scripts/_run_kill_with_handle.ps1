$tools = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'tools'
$env:Path = $env:Path + ";$tools"
Write-Output ("Temporarily added to PATH: {0}" -f $tools)
& "$(Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'tmp_kill_and_retry.ps1')"