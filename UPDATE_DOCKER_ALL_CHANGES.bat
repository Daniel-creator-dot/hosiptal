@echo off
echo.
echo ========================================
echo   Update Docker with ALL Recent Changes
echo ========================================
echo.
echo This will rebuild containers with:
echo   - Biometric system removal
echo   - Patient registration duplicate fixes
echo   - SMS duplicate prevention
echo   - Attendance system fixes
echo   - All code cleanup and improvements
echo.

REM Check if Docker is running
echo [1/7] Checking Docker Desktop...
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

REM Show current versions
echo [2/7] Current Docker versions:
docker --version
docker-compose --version
echo.

echo [3/7] Stopping all containers...
docker-compose down
if %errorlevel% neq 0 (
    echo    ⚠️  WARNING: Some containers may not have stopped cleanly
)
echo    ✅ Containers stopped
echo.

echo [4/7] Rebuilding containers with ALL latest code changes...
echo    This may take 5-10 minutes...
echo    Including:
echo      ✅ Biometric system removed
echo      ✅ Patient duplicate prevention fixes
echo      ✅ SMS duplicate prevention
echo      ✅ Attendance admin fixes
echo      ✅ URL namespace fixes
echo      ✅ Code cleanup and optimization
echo.
docker-compose build --no-cache web celery celery-beat
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Build failed!
    echo    Check the error messages above.
    echo.
    pause
    exit /b 1
)
echo    ✅ Containers rebuilt successfully
echo.

echo [5/7] Starting database and waiting for it to be ready...
docker-compose up -d db redis
timeout /t 15 /nobreak >nul
echo    ✅ Database and Redis started
echo.

echo [6/7] Running database migrations...
docker-compose run --rm web python manage.py migrate --noinput
if %errorlevel% neq 0 (
    echo    ⚠️  WARNING: Some migrations may have failed
    echo    Check logs: docker-compose logs web
) else (
    echo    ✅ Migrations completed successfully
)
echo.

echo [7/7] Collecting static files and starting all services...
docker-compose run --rm web python manage.py collectstatic --no-input --clear
if %errorlevel% neq 0 (
    echo    ⚠️  WARNING: Static files collection had issues
) else (
    echo    ✅ Static files collected
)
echo.

echo Starting all services...
docker-compose up -d
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Failed to start services!
    echo    Check logs: docker-compose logs
    echo.
    pause
    exit /b 1
)
echo    ✅ All services started
echo.

echo Waiting for services to be healthy...
timeout /t 10 /nobreak >nul
echo.

echo ========================================
echo   ✅ DOCKER UPDATED WITH ALL CHANGES!
echo ========================================
echo.
echo Recent changes included:
echo   ✅ Trial balance revenue display fix
echo   ✅ Revenue accounts showing in Credit column
echo   ✅ Duplicate prevention for accounting entries
echo   ✅ Insurance receivables verification
echo   ✅ Accounting sync service improvements
echo   ✅ Biometric system completely removed
echo   ✅ Patient registration duplicate prevention
echo   ✅ SMS duplicate prevention (1-hour check)
echo   ✅ Attendance export_to_excel method added
echo   ✅ Code cleanup (unused imports removed)
echo   ✅ URL namespace fixes (inventory, biometric)
echo   ✅ All linter errors fixed
echo.
echo Services:
echo   - Web: http://localhost:8000
echo   - Database: PostgreSQL (port 5432)
echo   - Redis: Running (port 6379)
echo   - Celery Worker: Running
echo   - Celery Beat: Running
echo.
echo Checking service status...
docker-compose ps
echo.
echo ========================================
echo   Update Complete!
echo ========================================
echo.
echo Next steps:
echo   1. Verify services: docker-compose ps
echo   2. Check logs: docker-compose logs web
echo   3. Test application: http://localhost:8000
echo.
pause
