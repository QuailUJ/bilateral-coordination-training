@echo off
setlocal
pushd "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Please double-click install.bat first.
    pause
    popd
    exit /b 1
)
".venv\Scripts\python.exe" main.py
set "result=%errorlevel%"
if not "%result%"=="0" (
    echo.
    echo Game stopped with an error. Keep this message for troubleshooting.
    pause
)
popd
exit /b %result%
