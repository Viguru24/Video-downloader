@echo off
setlocal
title OmniDownloader - Stop Server

echo ============================================================
echo    OmniDownloader - Stop / Free Port 8484
echo ============================================================
echo.

set "PORT=8484"

:: Terminate any process listening on port 8484 using native PowerShell
powershell -NoProfile -Command "$conns = Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue; if ($conns) { $conns | ForEach-Object { $p = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue; Write-Host ('  [+] Terminating ' + $p.ProcessName + ' (PID: ' + $_.OwningProcess + ')'); Stop-Process -Id $_.OwningProcess -Force }; Write-Host '  [+] Port %PORT% has been freed!' } else { Write-Host '  [i] Port %PORT% is not currently in use.' }"

echo.
echo Press any key to close...
pause >nul
