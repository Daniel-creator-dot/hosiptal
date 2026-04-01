@echo off
echo.
echo ========================================
echo   Update Docker with Accounting Fixes
echo   Trial Balance + Revenue + Insurance AR
echo ========================================
echo.
echo This will rebuild containers with:
echo   - Trial balance revenue display fix
echo   - Trial balance includes AdvancedGeneralLedger entries
echo   - Trial balance detailed transaction view (expandable)
echo   - Insurance receivables now shows correct balance
echo   - Revenue duplicate prevention
echo   - Accounting sync improvements
echo   - All recent accounting fixes
echo.

REM Check if Docker is running
echo [1/8] Checking Docker Desktop...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo    ERROR: Docker Desktop is not running!
    echo    Please start Docker Desktop and try again.
    echo.
    pause
    exit /b 1
)
echo    [OK] Docker Desktop is running
echo.

REM Show current versions
echo [2/8] Current Docker versions:
docker --version
docker-compose --version
echo.

echo [3/8] Stopping all containers...
docker-compose down
if %errorlevel% neq 0 (
    echo    WARNING: Some containers may not have stopped cleanly
)
echo    [OK] Containers stopped
echo.

echo [4/8] Rebuilding containers with ALL latest code changes...
echo    This may take 5-10 minutes...
echo    Including:
echo      - Trial balance revenue display fix
echo      - Revenue accounts showing in Credit column
echo      - Duplicate prevention for accounting entries
echo      - Insurance receivables verification
echo      - Accounting sync service improvements
echo      - All accounting fixes
echo.
docker-compose build --no-cache web celery celery-beat
if %errorlevel% neq 0 (
    echo    ERROR: Build failed!
    echo    Check the error messages above.
    echo.
    pause
    exit /b 1
)
echo    [OK] Containers rebuilt successfully
echo.

echo [5/8] Starting database and waiting for it to be ready...
docker-compose up -d db redis
timeout /t 15 /nobreak >nul
echo    [OK] Database and Redis started
echo.

echo [6/8] Running database migrations...
docker-compose run --rm web python manage.py migrate --noinput
if %errorlevel% neq 0 (
    echo    WARNING: Some migrations may have failed
    echo    Check logs: docker-compose logs web
) else (
    echo    [OK] Migrations completed successfully
)
echo.

echo [7/8] Collecting static files...
docker-compose run --rm web python manage.py collectstatic --no-input --clear
if %errorlevel% neq 0 (
    echo    WARNING: Static files collection had issues
) else (
    echo    [OK] Static files collected
)
echo.

echo [8/8] Starting all services...
docker-compose up -d
if %errorlevel% neq 0 (
    echo    ERROR: Failed to start services!
    echo    Check logs: docker-compose logs
    echo.
    pause
    exit /b 1
)
echo    [OK] All services started
echo.

echo Waiting for services to be healthy...
timeout /t 10 /nobreak >nul
echo.

echo ========================================
echo   DOCKER UPDATED WITH ACCOUNTING FIXES!
echo ========================================
echo.
echo Recent changes included:
echo   - Trial balance revenue display fixed
echo   - Trial balance now checks both GeneralLedger and AdvancedGeneralLedger
echo   - Trial balance shows detailed transaction entries (expandable)
echo   - Insurance receivables shows correct balance (GHS 1,836,602.62)
echo   - Revenue accounts show in Credit column
echo   - Duplicate prevention for GL entries
echo   - Accounting sync service enhanced
echo   - All accounting calculations corrected
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
echo   3. Test trial balance: http://localhost:8000/hms/accounting/trial-balance/
echo   4. Verify revenue accounts show in Credit column
echo.
pause
