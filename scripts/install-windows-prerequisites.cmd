@echo off
setlocal
cd /d "%~dp0.."

echo.
echo DB Allocation Utility - Windows prerequisite installer
echo Run as Administrator if installs fail.
echo.

where pwsh >nul 2>&1
if %ERRORLEVEL%==0 (
  pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-windows-prerequisites.ps1" %*
  exit /b %ERRORLEVEL%
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-windows-prerequisites.ps1" %*
exit /b %ERRORLEVEL%
