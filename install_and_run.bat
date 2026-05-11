@echo off
setlocal
pushd "%~dp0"

where powershell.exe >nul 2>nul
if errorlevel 1 (
    echo PowerShell was not found. Please install PowerShell or run install_and_run.ps1 manually.
    pause
    exit /b 1
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_and_run.ps1"
set "INSTALL_EXIT_CODE=%ERRORLEVEL%"

popd

if not "%INSTALL_EXIT_CODE%"=="0" (
    echo.
    echo Installer failed with exit code %INSTALL_EXIT_CODE%.
    pause
    exit /b %INSTALL_EXIT_CODE%
)

pause