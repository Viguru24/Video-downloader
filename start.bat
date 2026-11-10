@echo off
setlocal enabledelayedexpansion
title OmniDownloader - Universal Video Studio PWA

:: Ensure working directory is the script folder
cd /d "%~dp0"

echo ============================================================
echo    OmniDownloader - Universal Video Studio PWA
echo ============================================================
echo.

:: Detect Python executable (.venv, venv, system python, py launcher)
set "PYTHON_CMD="

if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_CMD=%~dp0.venv\Scripts\python.exe"
    goto :PYTHON_FOUND
)
if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_CMD=%~dp0venv\Scripts\python.exe"
    goto :PYTHON_FOUND
)

where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python"
    goto :PYTHON_FOUND
)

where py >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=py"
    goto :PYTHON_FOUND
)

echo [ERROR] Python was not found on your system PATH!
echo Please install Python 3.10+ from https://www.python.org/
echo or ensure Python is added to your PATH environment variable.
echo.
pause
exit /b 1

:PYTHON_FOUND
echo  [+] Python interpreter detected.

:: Check FFmpeg
where ffmpeg >nul 2>&1
if %errorlevel% equ 0 (
    echo  [+] FFmpeg detected.
) else (
    echo  [!] Warning: FFmpeg not found on PATH. High-res video/audio muxing may be limited.
)

:: Set Port
if "%PORT%"=="" (
    set "PORT=8484"
)

echo  [+] Web App URL: http://localhost:%PORT%
echo  [+] Launching OmniDownloader...
echo.

:: Open browser automatically
start "" "http://localhost:%PORT%"

:: Launch Server
"%PYTHON_CMD%" server.py

if %errorlevel% neq 0 (
    echo.
    echo [!] Server stopped with error code %errorlevel%.
    pause
)
