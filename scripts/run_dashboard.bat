@echo off
cd /d "%~dp0.."

echo Closing any previous dashboard server...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0kill_old_servers.ps1"

REM Also free port 8000 in case something else is holding it
for /f "tokens=5" %%p in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /F /PID %%p >nul 2>&1)

start "MRI Dashboard Server - close this window to stop" cmd /k python -m http.server 8000

timeout /t 2 /nobreak >nul

REM Cache-bust so the browser doesn't reuse a stale tab from an old folder/server
start "" "http://127.0.0.1:8000/index.html?t=%RANDOM%"
