@echo off
title Stop Qale
echo ===========================================
echo   Stopping Qale Developer Voice Assistant
echo ===========================================
echo.

:: 1. Force kill pythonw.exe (used by silent runner)
taskkill /F /IM pythonw.exe >nul 2>&1

:: 2. Terminate any python.exe running main.py
powershell -NoProfile -Command "Get-Process python -ErrorAction SilentlyContinue | Where-Object { try { (Get-CimInstance Win32_Process -Filter \"ProcessId=$($_.Id)\").CommandLine -like '*main.py*' } catch { $true } } | Stop-Process -Force" >nul 2>&1

echo [Qale] All background assistant processes stopped.
timeout /t 2 >nul

