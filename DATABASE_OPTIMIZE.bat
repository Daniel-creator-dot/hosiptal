@echo off
echo.
echo ========================================
echo   Database Optimization
echo ========================================
echo.

docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Docker Desktop is not running!
    pause
    exit /b 1
)

echo This will optimize the database (VACUUM, ANALYZE, REINDEX)
echo.
set /p confirm="Continue? (Y/N): "
if /i not "%confirm%"=="Y" (
    echo Cancelled.
    pause
    exit /b 0
)

docker-compose exec web python manage.py db_optimize --full

echo.
echo ✅ Optimization completed!
echo.
pause





