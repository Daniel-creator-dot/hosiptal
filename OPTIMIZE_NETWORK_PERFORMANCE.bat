@echo off
echo.
echo ========================================
echo   Network Performance Optimization
echo ========================================
echo.

REM Check if Docker is running
echo [1/3] Checking Docker Desktop...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Docker Desktop is not running!
    echo    Please start Docker Desktop and try again.
    echo.
    pause
    exit /b 1
)
echo    ✅ Docker Desktop is running
echo.

REM Clear cache to apply new optimizations
echo [2/3] Clearing cache for fresh start...
docker-compose exec web python manage.py shell -c "from django.core.cache import cache; cache.clear(); print('✅ Cache cleared')"
echo.

REM Restart web service to apply optimizations
echo [3/3] Restarting web service...
docker-compose restart web
echo.

echo ========================================
echo   ✅ OPTIMIZATION COMPLETE!
echo ========================================
echo.
echo Performance improvements applied:
echo   ✅ Database-level pagination (only loads 25 patients per page)
echo   ✅ Removed artificial limits (all patients can be shown)
echo   ✅ Extended cache duration (10 minutes)
echo   ✅ Optimized queries for network devices
echo.
echo The system should now load much faster on other devices!
echo.
pause





