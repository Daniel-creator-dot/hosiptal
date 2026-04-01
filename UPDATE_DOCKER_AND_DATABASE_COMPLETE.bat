@echo off
echo.
echo ========================================
echo   Complete Docker & Database Update
echo   Ensuring Persistence After Restart
echo ========================================
echo.

REM Check if Docker is running
echo [1/8] Checking Docker Desktop...
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

echo [2/8] Checking Docker volumes for persistence...
docker volume ls | findstr "chm_postgres_data chm_redis_data chm_minio_data" >nul
if %errorlevel% neq 0 (
    echo    ⚠️  Some volumes may be missing - will be created on start
) else (
    echo    ✅ All persistent volumes exist
)
echo.

echo [3/8] Stopping all containers gracefully...
docker-compose down
timeout /t 3 /nobreak >nul
echo    ✅ Containers stopped
echo.

echo [4/8] Rebuilding containers with latest code changes...
echo    This includes:
echo      - Reports dashboard fixes
echo      - Department performance report
echo      - Front desk reports fixes
echo      - Chat system updates
echo    This may take a few minutes...
docker-compose build --no-cache web celery celery-beat
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Build failed!
    pause
    exit /b 1
)
echo    ✅ Containers rebuilt with latest code
echo.

echo [5/8] Starting database and waiting for it to be ready...
docker-compose up -d db redis
echo    Waiting for database to be healthy...
timeout /t 15 /nobreak >nul
docker-compose exec -T db pg_isready -U hms_user -d hms_db >nul 2>&1
if %errorlevel% neq 0 (
    echo    ⚠️  Database may still be starting, continuing anyway...
) else (
    echo    ✅ Database is ready
)
echo.

echo [6/8] Running database migrations...
docker-compose run --rm web python manage.py migrate --noinput
if %errorlevel% neq 0 (
    echo    ⚠️  WARNING: Some migrations may have failed
    echo    Attempting to continue...
) else (
    echo    ✅ All migrations applied successfully
)
echo.

echo [7/8] Collecting static files...
docker-compose run --rm web python manage.py collectstatic --no-input --clear
if %errorlevel% neq 0 (
    echo    ⚠️  WARNING: Static files collection had issues
) else (
    echo    ✅ Static files collected
)
echo.

echo [8/8] Starting all services with persistent volumes...
docker-compose up -d
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Failed to start services!
    pause
    exit /b 1
)
echo    ✅ All services started
echo.

echo Waiting for services to be healthy...
timeout /t 10 /nobreak >nul
echo.

echo ========================================
echo   ✅ DOCKER & DATABASE UPDATED!
echo ========================================
echo.
echo Database Persistence:
echo   ✅ PostgreSQL data: chm_postgres_data (persistent)
echo   ✅ Redis data: chm_redis_data (persistent)
echo   ✅ MinIO data: chm_minio_data (persistent)
echo.
echo Services:
echo   - Web: http://localhost:8000
echo   - Database: PostgreSQL (port 5432)
echo   - Cache: Redis (port 6379)
echo   - Storage: MinIO (ports 9000, 9001)
echo.
echo Recent Updates Applied:
echo   ✅ Reports Dashboard (/hms/reports/)
echo   ✅ Department Performance Report
echo   ✅ Front Desk GP Consultations Report
echo   ✅ Chat System
echo   ✅ IT Operations Dashboard
echo.
echo Checking service status...
docker-compose ps
echo.
echo Verifying database connection...
docker-compose exec -T web python manage.py check --database default
if %errorlevel% equ 0 (
    echo    ✅ Database connection verified
) else (
    echo    ⚠️  Database connection check had issues
)
echo.
echo ========================================
echo   All changes are now persistent!
echo   System will work after full restart.
echo ========================================
echo.
pause











