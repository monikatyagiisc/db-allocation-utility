@echo off
setlocal
cd /d "%~dp0.."

where pwsh >nul 2>&1
if %ERRORLEVEL%==0 (
  pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-local.ps1" %*
  exit /b %ERRORLEVEL%
)

where powershell >nul 2>&1
if %ERRORLEVEL%==0 (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-local.ps1" %*
  exit /b %ERRORLEVEL%
)

echo xx^> PowerShell is required. Install PowerShell 5.1+ or PowerShell 7 (pwsh).
exit /b 1
