@echo off
title NovaShift Launcher

cd /d "%~dp0"

if not exist "app.py" (
    echo ERROR: app.py not found!
    pause
    exit
)

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Python virtual environment not found!
    pause
    exit
)

set "PATH=%PATH%;%USERPROFILE%\Desktop\YouTube Download"

echo Starting NovaShift...

start "" cmd /c "timeout /t 4 /nobreak >nul & start http://127.0.0.1:5000"

".venv\Scripts\python.exe" app.py

pause