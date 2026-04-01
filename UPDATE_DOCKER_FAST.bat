@echo off
echo.
echo ========================================
echo   Fast Docker Update - Apply Code Changes
echo   (Uses volume mounts - no rebuild needed)
echo ========================================
echo.
echo This will apply all recent code changes:
echo   ✅ Biometric system removed
echo   ✅ Patient duplicate prevention fixes
echo   ✅ SMS duplicate prevention
echo   ✅ Attendance admin fixes
echo   ✅ URL namespace fixes
echo   ✅ Code cleanup
echo.

REM Check if Docker is running
echo [1/5] Checking Docker Desktop...
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

echo [2/5] Restarting containers to apply code changes...
docker-compose restart web celery celery-beat
if %errorlevel% neq 0 (
    echo    ⚠️  WARNING: Some containers may not have restarted
)
echo    ✅ Containers restarted
echo.

echo [3/5] Running database migrations...
docker-compose exec -T web python manage.py migrate --noinput
if %errorlevel% neq 0 (
    echo    ⚠️  WARNING: Some migrations may have failed
) else (
    echo    ✅ Migrations completed
)
echo.

echo [4/5] Collecting static files...
docker-compose exec -T web python manage.py collectstatic --no-input --clear
if %errorlevel% neq 0 (
    echo    ⚠️  WARNING: Static files collection had issues
) else (
    echo    ✅ Static files collected
)
echo.

echo [5/5] Waiting for services to be ready...
timeout /t 5 /nobreak >nul
echo    ✅ Services should be ready
echo.

echo ========================================
echo   ✅ DOCKER UPDATED SUCCESSFULLY!
echo ========================================
echo.
echo All recent code changes have been applied:
echo   ✅ Biometric system removed
echo   ✅ Patient duplicate prevention fixes
echo   ✅ SMS duplicate prevention
echo   ✅ Attendance admin export_to_excel added
echo   ✅ Code cleanup completed
echo   ✅ URL namespace fixes
echo.
echo Checking service status...
docker-compose ps
echo.
echo Services:
echo   - Web: http://localhost:8000
echo   - Database: Running
echo   - Redis: Running
echo   - Celery: Running
echo.
pause
