@echo off
setlocal enabledelayedexpansion
title OmniDownloader - Universal Video Studio PWA

:: Ensure working directory is the script folder
cd /d "%~dp0"

echo ============================================================
echo    OmniDownloader - Universal Video Studio PWA
echo ============================================================
echo.

:: Detect valid Python executable (exclude broken WindowsApps alias)
set "PYTHON_CMD="

:: 1. Check local virtual environments first
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" -c "import sys" >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=%~dp0.venv\Scripts\python.exe"
        goto :PYTHON_FOUND
    )
)
if exist "%~dp0venv\Scripts\python.exe" (
    "%~dp0venv\Scripts\python.exe" -c "import sys" >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=%~dp0venv\Scripts\python.exe"
        goto :PYTHON_FOUND
    )
)

:: 2. Check standard Program Files installations (Python 3.12 / 3.14)
if exist "C:\Program Files\Python312\python.exe" (
    "C:\Program Files\Python312\python.exe" -c "import sys" >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=C:\Program Files\Python312\python.exe"
        goto :PYTHON_FOUND
    )
)
if exist "C:\Program Files\Python314\python.exe" (
    "C:\Program Files\Python314\python.exe" -c "import sys" >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=C:\Program Files\Python314\python.exe"
        goto :PYTHON_FOUND
    )
)

:: 3. Check Python launcher (py)
where py >nul 2>&1
if %errorlevel% equ 0 (
    py -3.12 -c "import sys" >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=py -3.12"
        goto :PYTHON_FOUND
    )
    py -3.14 -c "import sys" >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=py -3.14"
        goto :PYTHON_FOUND
    )
    py -c "import sys" >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=py"
        goto :PYTHON_FOUND
    )
)

:: 4. Check system python in PATH (skip WindowsApps shim)
for /f "tokens=*" %%i in ('where python 2^>nul') do (
    echo "%%i" | findstr /i "WindowsApps" >nul
    if !errorlevel! neq 0 (
        "%%i" -c "import sys" >nul 2>&1
        if !errorlevel! equ 0 (
            set "PYTHON_CMD=%%i"
            goto :PYTHON_FOUND
        )
    )
)

echo [ERROR] No working Python installation detected!
echo Please install Python 3.10+ from https://www.python.org/
echo or disable the Windows Store App execution alias in:
echo Windows Settings > Apps > Advanced app settings > App execution aliases.
echo.
pause
exit /b 1

:PYTHON_FOUND
echo  [+] Python interpreter: %PYTHON_CMD%

:: Verify required modules
%PYTHON_CMD% -c "import uvicorn, yt_dlp, fastapi" >nul 2>&1
if %errorlevel% neq 0 (
    echo  [*] Installing required packages from requirements.txt...
    %PYTHON_CMD% -m pip install -r "%~dp0requirements.txt"
)

:: Check FFmpeg
where ffmpeg >nul 2>&1
if %errorlevel% equ 0 (
    echo  [+] FFmpeg detected.
) else (
    echo  [!] Warning: FFmpeg not found on PATH. Video muxing may be limited.
)

:: Set Port
if "%PORT%"=="" (
    set "PORT=8484"
)

echo  [+] App URL: http://localhost:%PORT%
echo  [+] Starting server (browser will open automatically once ready)...
echo.

:: Open browser after 2 seconds in background to allow uvicorn to bind port
start "" /B cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:%PORT%"

:: Launch Server
%PYTHON_CMD% server.py

if %errorlevel% neq 0 (
    echo.
    echo [!] Server stopped with error code %errorlevel%.
    pause
)
