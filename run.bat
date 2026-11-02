@echo off
chcp 65001 >nul
title Qale Voice-to-Code Assistant
setlocal

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

:: Set Python environment path
if exist "%LOCALAPPDATA%\Programs\Python\Python313\Lib\encodings" (
    set "PYTHONHOME=%LOCALAPPDATA%\Programs\Python\Python313"
) else if exist "C:\Users\HP Victus\AppData\Local\Programs\Python\Python313\Lib\encodings" (
    set "PYTHONHOME=C:\Users\HP Victus\AppData\Local\Programs\Python\Python313"
) else if exist "C:\Python313\Lib\encodings" (
    set "PYTHONHOME=C:\Python313"
)

if exist "C:\Python313\python.exe" (
    set "PYTHON_EXE=C:\Python313\python.exe"
    set "PATH=C:\Python313;%PYTHONHOME%;%PYTHONHOME%\Scripts;%PATH%"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python313;%LOCALAPPDATA%\Programs\Python\Python313\Scripts;%PATH%"
) else (
    set "PYTHON_EXE=python"
)

echo ===================================================
echo   Qale - Developer Voice-to-Code Assistant
echo   GPU: NVIDIA GeForce RTX 2050 (Accelerated)
echo ===================================================
echo.

"%PYTHON_EXE%" main.py %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [Qale] App exited with an error. Press any key to close...
    pause >nul
)
