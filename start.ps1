# OmniDownloader Windows Launch Script
$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  🚀 Launching OmniDownloader PWA..." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

# Test if ffmpeg is in path
try {
    $ffmpegVer = ffmpeg -version
    Write-Host "  ✓ FFmpeg detected." -ForegroundColor DarkGreen
} catch {
    Write-Host "  ⚠ FFmpeg not found on PATH. Some video merging might be limited." -ForegroundColor Yellow
}

# Start server
$env:PORT = "8484"
python server.py
