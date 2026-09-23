@echo off
title MoonBite Miner
cd /d "%~dp0"
echo ======================================================================
echo  MoonBite solo miner
echo  Starting your node and mining now. This window IS the miner -
echo  closing it stops mining. Leave it open.
echo ======================================================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0mine.ps1" %*
echo.
echo ======================================================================
echo  The miner stopped. If that was not on purpose, read any error above.
echo ======================================================================
pause
