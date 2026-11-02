@echo off
title Restart Qale
echo ===========================================
echo   Restarting Qale Voice Assistant...
echo ===========================================
echo.

:: 1. Stop existing process
taskkill /F /IM pythonw.exe >nul 2>&1
powershell -NoProfile -Command "Get-Process python -ErrorAction SilentlyContinue | Where-Object { try { (Get-CimInstance Win32_Process -Filter \"ProcessId=$($_.Id)\").CommandLine -like '*main.py*' } catch { $true } } | Stop-Process -Force" >nul 2>&1

:: 2. Wait a moment
timeout /t 1 >nul

:: 3. Launch silent background runner
start "" wscript.exe "%~dp0run_silent.vbs"

echo [Qale] Restarted silently in background!
timeout /t 2 >nul

