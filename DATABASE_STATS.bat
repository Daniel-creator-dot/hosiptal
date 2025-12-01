@echo off
echo.
echo ========================================
echo   Database Statistics
echo ========================================
echo.

docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Docker Desktop is not running!
    pause
    exit /b 1
)

docker-compose exec web python manage.py db_stats

pause





