@echo off
echo.
echo ========================================
echo   World-Class Database Backup
echo ========================================
echo.

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Docker Desktop is not running!
    pause
    exit /b 1
)

echo Creating database backup...
docker-compose exec web python manage.py db_backup --compress --cleanup --keep-days 30

echo.
echo ✅ Backup completed!
echo.
pause





