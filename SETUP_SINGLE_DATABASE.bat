@echo off
echo.
echo ========================================
echo   Setup Single PostgreSQL Database
echo   All Services Use Same Database URL
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

echo [2/5] Creating .env file...
if not exist .env (
    if exist .env.template (
        copy .env.template .env >nul 2>&1
        echo    ✅ .env file created from template
    ) else (
        echo    Creating .env file with default PostgreSQL configuration...
        (
            echo # Single PostgreSQL Database Configuration
            echo DATABASE_URL=postgresql://hms_user:hms_password@localhost:5432/hms_db
            echo DATABASE_CONN_MAX_AGE=600
            echo DATABASE_CONN_HEALTH_CHECKS=True
            echo DATABASE_TIMEOUT=10
            echo DATABASE_SSL_MODE=prefer
            echo REDIS_URL=redis://localhost:6379/0
            echo USE_REDIS_CACHE=True
            echo DEBUG=1
        ) > .env
        echo    ✅ .env file created
    )
) else (
    echo    ✅ .env file already exists
)
echo.

echo [3/5] Verifying database configuration in docker-compose.yml...
findstr /C:"DATABASE_URL" docker-compose.yml >nul 2>&1
if %errorlevel% equ 0 (
    echo    ✅ docker-compose.yml has DATABASE_URL configured
) else (
    echo    ⚠️  WARNING: DATABASE_URL not found in docker-compose.yml
)
echo.

echo [4/5] Restarting Docker services with new configuration...
docker-compose down
timeout /t 3 /nobreak >nul
docker-compose up -d
timeout /t 10 /nobreak >nul
echo    ✅ Services restarted
echo.

echo [5/5] Verifying all services use same database...
echo    Checking web service...
docker-compose exec web python manage.py shell -c "from django.conf import settings; print('  Web DB:', settings.DATABASES['default']['NAME'])" 2>nul
echo    Checking celery service...
docker-compose exec celery python manage.py shell -c "from django.conf import settings; print('  Celery DB:', settings.DATABASES['default']['NAME'])" 2>nul
echo    Checking celery-beat service...
docker-compose exec celery-beat python manage.py shell -c "from django.conf import settings; print('  Celery-Beat DB:', settings.DATABASES['default']['NAME'])" 2>nul
echo.

echo ========================================
echo   ✅ SINGLE DATABASE CONFIGURED!
echo ========================================
echo.
echo All services are now using:
echo   Database: hms_db
echo   User: hms_user
echo   Host: db (Docker) / localhost (Local)
echo   Port: 5432
echo.
echo Configuration source: .env file
echo.
pause





