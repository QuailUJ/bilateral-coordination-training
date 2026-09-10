@echo off
setlocal
pushd "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1"
    if errorlevel 1 (
        pause
        popd
        exit /b 1
    )
)
".venv\Scripts\python.exe" elbow_angle_tracker.py
set "result=%errorlevel%"
if not "%result%"=="0" (
    echo.
    echo Tracker stopped with an error. For missing packages, run install.bat again.
    pause
)
popd
exit /b %result%
