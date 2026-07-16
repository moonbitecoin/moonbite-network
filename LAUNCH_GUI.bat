@echo off
REM MoonBite Desktop GUI Launcher

cd C:\Users\usman\Desktop\MoonBite

REM Check if shared_state.py is already running
tasklist | findstr "python.exe" >nul 2>&1
if errorlevel 1 (
    REM No Python processes running, start shared_state.py
    echo Starting shared state server...
    python shared_state.py >nul 2>&1 &
    timeout /t 2 /nobreak >nul
)

REM Start the GUI
echo Starting MoonBite Desktop GUI...
python gui_shared.py

REM Keep window open if GUI closes
pause
