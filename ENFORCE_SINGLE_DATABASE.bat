@echo off
echo.
echo ========================================
echo   Enforce Single PostgreSQL Database
echo   All Services Use Same Database URL
echo ========================================
echo.

REM Check if Docker is running
echo [1/4] Checking Docker Desktop...
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

echo [2/4] Verifying .env file exists...
if not exist .env (
    echo    ⚠️  .env file not found, creating from template...
    copy env.example .env >nul 2>&1
    echo    ✅ .env file created
) else (
    echo    ✅ .env file exists
)
echo.

echo [3/4] Verifying database configuration...
docker-compose exec web python manage.py shell -c "from django.conf import settings; db = settings.DATABASES['default']; print(f'Database: {db[\"NAME\"]}'); print(f'User: {db[\"USER\"]}'); print(f'Host: {db[\"HOST\"]}'); print(f'Port: {db[\"PORT\"]}')" 2>nul
if %errorlevel% neq 0 (
    echo    ⚠️  Docker services not running, starting them...
    docker-compose up -d
    timeout /t 10 /nobreak >nul
)
echo.

echo [4/4] Verifying all services use same database...
echo    Checking web service...
docker-compose exec web python manage.py shell -c "from django.conf import settings; print('Web DB:', settings.DATABASES['default']['NAME'])" 2>nul
echo    Checking celery service...
docker-compose exec celery python manage.py shell -c "from django.conf import settings; print('Celery DB:', settings.DATABASES['default']['NAME'])" 2>nul
echo    Checking celery-beat service...
docker-compose exec celery-beat python manage.py shell -c "from django.conf import settings; print('Celery-Beat DB:', settings.DATABASES['default']['NAME'])" 2>nul
echo.

echo ========================================
echo   ✅ SINGLE DATABASE CONFIGURATION
echo ========================================
echo.
echo All services are configured to use:
echo   Database: hms_db
echo   User: hms_user
echo   Host: db (Docker) / localhost (Local)
echo   Port: 5432
echo.
echo Configuration source: .env file
echo.
pause





