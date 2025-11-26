@echo off
REM Thin wrapper that invokes the PowerShell launcher for robust startup
SETLOCAL
SET "PS1=%~dp0system_manager.ps1"
if exist "%PS1%" (
	powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
) else (
	echo Missing %PS1% - cannot launch services.
	pause
)
ENDLOCAL
