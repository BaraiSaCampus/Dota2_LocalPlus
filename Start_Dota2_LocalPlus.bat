@echo off
setlocal
pushd "%~dp0"

if exist "%~dp0Dota2_LocalPlus.exe" (
    start "Dota2 LocalPlus" "%~dp0Dota2_LocalPlus.exe"
    popd
    exit /b 0
)

if exist "%~dp0install_and_run.bat" (
    echo Portable executable not found. Starting one-click setup...
    call "%~dp0install_and_run.bat"
    set "START_EXIT_CODE=%ERRORLEVEL%"
    popd
    exit /b %START_EXIT_CODE%
)

echo Dota2_LocalPlus.exe is missing. Please extract the complete portable package and try again.
pause
popd
exit /b 1
