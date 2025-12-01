try {
    $repo = Split-Path -Parent $MyInvocation.MyCommand.Path
    $toolsDir = Join-Path $repo 'tools'
    New-Item -Path $toolsDir -ItemType Directory -Force | Out-Null
    $zipPath = Join-Path $toolsDir 'handle.zip'
    $outLog = Join-Path $repo '..\results\handle_download_result.txt' | Resolve-Path -ErrorAction SilentlyContinue
    Invoke-WebRequest -Uri 'https://download.sysinternals.com/files/Handle.zip' -OutFile $zipPath -UseBasicParsing -ErrorAction Stop
    Expand-Archive -LiteralPath $zipPath -DestinationPath $toolsDir -Force
    "$((Get-Item (Join-Path $toolsDir 'handle.exe')).FullName)" | Out-File -FilePath (Join-Path $repo '..\results\handle_download_result.txt') -Encoding utf8
} catch {
    $err = $_ | Out-String
    $err | Out-File -FilePath (Join-Path $repo '..\results\handle_download_error.txt') -Encoding utf8
    exit 1
}