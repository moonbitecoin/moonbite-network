@echo off
title MoonBite Reactor
cd /d "%~dp0"
where py >nul 2>nul && ( py moonbite_reactor.py & goto :eof )
where python >nul 2>nul && ( python moonbite_reactor.py & goto :eof )
echo Python 3 was not found on this PC.
echo Install it from https://www.python.org/downloads/ and run this file again.
pause
