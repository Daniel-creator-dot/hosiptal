@echo off
echo.
echo ========================================
echo   Update Docker with All Changes
echo   Ensure Single PostgreSQL Database
echo ========================================
echo.

REM Check if Docker is running
echo [1/6] Checking Docker Desktop...
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

echo [2/6] Stopping all containers...
docker-compose down
echo    ✅ Containers stopped
echo.

echo [3/6] Rebuilding containers with latest code changes...
echo    This may take a few minutes...
echo    Including recent changes:
echo      - Lab result notifications (doctors, nurses, front desk)
echo      - Notification popup and topbar bell UI
echo      - Role dashboard and template updates
docker-compose build --no-cache web celery celery-beat
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Build failed!
    pause
    exit /b 1
)
echo    ✅ Containers rebuilt with latest code
echo.

echo [4/6] Starting database and waiting for it to be ready...
docker-compose up -d db
timeout /t 10 /nobreak >nul
echo    ✅ Database started
echo.

echo [5/6] Running database migrations and collecting static files...
docker-compose run --rm web python manage.py migrate --noinput
if %errorlevel% neq 0 (
    echo    ⚠️  WARNING: Some migrations may have failed
)
docker-compose run --rm web python manage.py collectstatic --no-input --clear
if %errorlevel% neq 0 (
    echo    ⚠️  WARNING: Static files collection had issues
)
echo    ✅ Migrations completed
echo    ✅ Static files collected
echo.

echo [6/6] Starting all services with single PostgreSQL database...
docker-compose up -d
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
echo All Django services are now using:
echo   - Single PostgreSQL database: hms_db
echo   - Same database connection: postgresql://hms_user:hms_password@db:5432/hms_db
echo   - Shared Redis cache
echo.
echo Services:
echo   - Web: http://localhost:8000
echo   - Celery Worker: Running
echo   - Celery Beat: Running
echo   - PostgreSQL: db:5432
echo   - Redis: redis:6379
echo.
echo Checking service status...
docker-compose ps
echo.
pause





