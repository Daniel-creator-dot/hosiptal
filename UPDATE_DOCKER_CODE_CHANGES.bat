@echo off
echo.
echo ========================================
echo   Quick Docker Update - Code Changes
echo   Rebuilds containers with latest code
echo ========================================
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

echo [2/5] Stopping containers...
docker-compose stop web celery celery-beat
echo    ✅ Containers stopped
echo.

echo [3/5] Rebuilding containers with latest code changes...
echo    This may take a few minutes...
docker-compose build web celery celery-beat
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Build failed!
    pause
    exit /b 1
)
echo    ✅ Containers rebuilt with latest code
echo.

echo [4/5] Collecting static files (templates, CSS, JS)...
docker-compose run --rm web python manage.py collectstatic --no-input --clear
if %errorlevel% neq 0 (
    echo    ⚠️  WARNING: Static files collection had issues
)
echo    ✅ Static files collected
echo.

echo [5/5] Starting services...
docker-compose up -d web celery celery-beat
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Failed to start services!
    pause
    exit /b 1
)
echo    ✅ All services started
echo.

echo ========================================
echo   ✅ DOCKER UPDATED SUCCESSFULLY!
echo ========================================
echo.
echo Changes included:
echo   - Role dashboard updates
echo   - Template changes
echo   - URL routing updates
echo   - View updates
echo   - Live sessions duplicate fix
echo   - Session timeout improvements
echo   - Database stability enhancements
echo   - Admin display improvements
echo   - Staff management fixes
echo.
echo Services:
echo   - Web: http://localhost:8000
echo   - Celery Worker: Running
echo   - Celery Beat: Running
echo.
echo Checking service status...
docker-compose ps
echo.
pause

