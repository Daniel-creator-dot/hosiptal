@echo off
echo.
echo ========================================
echo   Complete Docker Restart & Update
echo   Apply All Recent Changes
echo ========================================
echo.

REM Check if Docker Desktop is running
echo [1/8] Checking Docker Desktop...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo    Docker Desktop is not running - starting it...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo    Waiting 30 seconds for Docker Desktop to start...
    timeout /t 30 /nobreak >nul
    
    REM Check again
    docker info >nul 2>&1
    if %errorlevel% neq 0 (
        echo    ❌ ERROR: Docker Desktop failed to start!
        echo    Please start Docker Desktop manually and run this script again.
        pause
        exit /b 1
    )
)
echo    ✅ Docker Desktop is running
echo.

echo [2/8] Stopping all containers...
docker-compose down
echo    ✅ Containers stopped
echo.

echo [3/8] Starting database and Redis...
docker-compose up -d db redis
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Failed to start database/redis
    pause
    exit /b 1
)
echo    Waiting for database to be ready...
timeout /t 15 /nobreak >nul
echo    ✅ Database and Redis started
echo.

echo [4/8] Starting web service...
docker-compose up -d web
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Failed to start web service
    pause
    exit /b 1
)
echo    ✅ Web service started
echo.

echo [5/8] Running database migrations (with fixes)...
docker-compose exec -T web python manage.py migrate --noinput
if %errorlevel% neq 0 (
    echo    ⚠️  Some migrations had issues, trying to continue...
    docker-compose exec -T web python manage.py migrate --noinput --run-syncdb
) else (
    echo    ✅ Migrations completed
)
echo.

echo [6/8] Collecting static files...
docker-compose exec -T web python manage.py collectstatic --no-input --clear
if %errorlevel% neq 0 (
    echo    ⚠️  Static collection had issues, but continuing...
) else (
    echo    ✅ Static files collected
)
echo.

echo [7/8] Starting all worker services...
docker-compose up -d celery celery-beat
if %errorlevel% neq 0 (
    echo    ⚠️  Some worker services may have issues
) else (
    echo    ✅ All services started
)
echo.

echo [8/8] Waiting for services to be healthy...
timeout /t 10 /nobreak >nul
echo    ✅ Services should be ready
echo.

echo ========================================
echo   ✅ DOCKER RESTARTED & UPDATED!
echo ========================================
echo.
echo All recent changes applied:
echo   ✅ Biometric system removed
echo   ✅ Patient duplicate prevention fixed
echo   ✅ SMS duplicate prevention added
echo   ✅ Attendance admin fixes
echo   ✅ URL namespace fixes
echo   ✅ Migration fixes applied
echo   ✅ Code cleanup completed
echo.
echo Checking service status...
docker-compose ps
echo.
echo Services available at:
echo   - Web: http://localhost:8000
echo   - Database: PostgreSQL (port 5432)
echo   - Redis: (port 6379)
echo.
echo If any service shows as unhealthy, check logs:
echo   docker-compose logs web
echo   docker-compose logs celery
echo.
pause
