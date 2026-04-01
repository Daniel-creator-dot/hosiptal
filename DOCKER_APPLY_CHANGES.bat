@echo off
echo.
echo ========================================
echo   Apply Code Changes to Docker
echo   (Restart containers - no rebuild)
echo ========================================
echo.

docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker Desktop is not running. Start it and try again.
    pause
    exit /b 1
)

echo Restarting web, celery, and celery-beat to pick up latest code...
docker compose restart web celery celery-beat
if %errorlevel% neq 0 (
    echo Try: docker compose up -d
    pause
    exit /b 1
)

echo.
echo Done. Your changes (notifications, templates, static files) are now live.
echo.
pause
