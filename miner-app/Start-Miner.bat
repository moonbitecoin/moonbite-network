@echo off
REM MoonBite CPU Miner - one double-click to start.
REM Asks for your reward address, then runs a local node and mines to it.
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python 3 is required but was not found on PATH.
  echo Install it from https://www.python.org/downloads/ and run this again.
  pause
  exit /b 1
)

python "%~dp0moonbite-miner.py" %*
echo.
pause
