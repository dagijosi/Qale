@echo off
chcp 65001 >nul
title Qale Environment Setup
setlocal

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

:: Set Python environment
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
echo   Installing Qale Dependencies...
echo ===================================================
echo.

"%PYTHON_EXE%" -m pip install --upgrade pip
"%PYTHON_EXE%" -m pip install sounddevice numpy keyboard pynput pystray Pillow faster-whisper openai-whisper pywebview

echo.
echo ===================================================
echo   Setup completed! You can now run run.bat
echo ===================================================
pause
