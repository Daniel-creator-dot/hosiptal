@echo off
echo.
echo ========================================
echo   Database Health Check
echo ========================================
echo.

docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Docker Desktop is not running!
    pause
    exit /b 1
)

docker-compose exec web python manage.py db_health_check --detailed

pause





