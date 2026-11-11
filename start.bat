@echo off
setlocal
title OmniDownloader - Universal Video Studio PWA

:: Ensure working directory is the script folder
cd /d "%~dp0"

echo ============================================================
echo    OmniDownloader - Universal Video Studio PWA
echo ============================================================
echo.

set "PORT=8484"
set "PYTHON_EXE="
set "PYTHON_ARG="

:: Check if OmniDownloader is already running on port 8484
netstat -ano | findstr /c:":%PORT% " | findstr /i "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo  [+] OmniDownloader is already active on port %PORT%!
    echo  [+] Opening browser at http://localhost:%PORT% ...
    start "" "http://localhost:%PORT%"
    echo.
    echo Press any key to exit this launcher window.
    pause >nul
    exit /b 0
)

:: 1. Check local virtual environments first
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
    goto :PYTHON_FOUND
)
if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
    goto :PYTHON_FOUND
)

:: 2. Check standard Program Files installations (Python 3.12 / 3.14)
if exist "C:\Program Files\Python312\python.exe" (
    set "PYTHON_EXE=C:\Program Files\Python312\python.exe"
    goto :PYTHON_FOUND
)
if exist "C:\Program Files\Python314\python.exe" (
    set "PYTHON_EXE=C:\Program Files\Python314\python.exe"
    goto :PYTHON_FOUND
)

:: 3. Check AppData installations
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto :PYTHON_FOUND
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    goto :PYTHON_FOUND
)

:: 4. Check Python launcher (py)
where py >nul 2>&1
if %errorlevel% equ 0 (
    py -3.12 -c "import sys" >nul 2>&1
    if %errorlevel% equ 0 (
        set "PYTHON_EXE=py"
        set "PYTHON_ARG=-3.12"
        goto :PYTHON_FOUND
    )
    py -3.14 -c "import sys" >nul 2>&1
    if %errorlevel% equ 0 (
        set "PYTHON_EXE=py"
        set "PYTHON_ARG=-3.14"
        goto :PYTHON_FOUND
    )
    py -c "import sys" >nul 2>&1
    if %errorlevel% equ 0 (
        set "PYTHON_EXE=py"
        goto :PYTHON_FOUND
    )
)

:: 5. Check system python in PATH (skip WindowsApps alias)
for /f "tokens=*" %%i in ('where python 2^>nul') do (
    echo "%%i" | findstr /i "WindowsApps" >nul
    if %errorlevel% neq 0 (
        "%%i" -c "import sys" >nul 2>&1
        if %errorlevel% equ 0 (
            set "PYTHON_EXE=%%i"
            goto :PYTHON_FOUND
        )
    )
)

echo [ERROR] No working Python installation detected.
echo Please install Python 3.10+ from https://www.python.org/
echo.
pause
exit /b 1

:PYTHON_FOUND
if "%PYTHON_ARG%"=="" (
    set RUN_PY="%PYTHON_EXE%"
) else (
    set RUN_PY="%PYTHON_EXE%" %PYTHON_ARG%
)

echo  [+] Python interpreter detected: %RUN_PY%

:: Verify required modules
%RUN_PY% -c "import uvicorn, yt_dlp, fastapi" >nul 2>&1
if %errorlevel% neq 0 (
    echo  [*] Installing required packages from requirements.txt...
    %RUN_PY% -m pip install -r "%~dp0requirements.txt"
)

:: Check FFmpeg
where ffmpeg >nul 2>&1
if %errorlevel% equ 0 (
    echo  [+] FFmpeg detected.
) else (
    echo  [!] Warning: FFmpeg not found on PATH. Video muxing may be limited.
)

echo  [+] App URL: http://localhost:%PORT%
echo  [+] Starting server (browser will open automatically once ready)...
echo.

:: Open browser after 2 seconds in background
start "" /B cmd /c "ping 127.0.0.1 -n 3 >nul & start http://localhost:%PORT%"

:: Launch Server
%RUN_PY% server.py

if %errorlevel% neq 0 (
    echo.
    echo [!] Server stopped with error code %errorlevel%.
    pause
)
