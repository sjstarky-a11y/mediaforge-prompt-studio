@echo off
setlocal
cd /d "%~dp0"
title MediaForge Prompt Studio

echo.
echo MediaForge Prompt Studio
echo ========================

if /I "%~1"=="install" goto install
if /I "%~1"=="start" goto start
if /I "%~1"=="status" goto status
if /I "%~1"=="stop" goto stop

if not exist ".env" goto install
goto start

:install
echo Preparing MediaForge for first use...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
goto result

:start
echo Starting MediaForge...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
goto result

:status
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0status.ps1"
goto result

:stop
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop.ps1"
goto result

:result
if errorlevel 1 goto failed
exit /b 0

:failed
echo.
echo MediaForge could not complete the requested action.
echo Review the message above, then run this launcher again.
echo.
pause
exit /b 1
