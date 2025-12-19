<# Helper: wsl_check_features_elevated.ps1
   Run elevated to write the WSL/VM feature states to temp files for inspection.
#>

Get-WindowsOptionalFeature -Online -FeatureName 'Microsoft-Windows-Subsystem-Linux' | Out-File -FilePath "$env:TEMP\wsl_feat1.txt" -Encoding UTF8
Get-WindowsOptionalFeature -Online -FeatureName 'VirtualMachinePlatform' | Out-File -FilePath "$env:TEMP\wsl_feat2.txt" -Encoding UTF8
Write-Output 'Feature check complete.'
