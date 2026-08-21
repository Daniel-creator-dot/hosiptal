@echo off
title HMS Server - C:\chm (SSD)
cd /d C:\chm
if not exist C:\chm\docker-compose.yml (
    echo ERROR: C:\chm\docker-compose.yml not found.
    pause
    exit /b 1
)
echo Verifying HMS runs from C:\chm...
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\chm\scripts\ensure_c_chm.ps1" -Fix -Quiet
if errorlevel 1 (
    echo Failed to start HMS from C:\chm.
    pause
    exit /b 1
)
echo Starting HMS from C:\chm (SSD)...
docker compose up -d
echo.
echo Waiting for web service...
timeout /t 60 /nobreak >nul
docker compose ps
echo.
echo Hospital app: http://192.168.2.216:8000
echo Local:        http://localhost:8000
pause
