@echo off
REM Quick fix script for PostgreSQL Desktop setup
echo ========================================
echo PostgreSQL Desktop Setup
echo ========================================
echo.

echo Step 1: Checking PostgreSQL Desktop...
netstat -an | findstr 5432 >nul
if %errorlevel% neq 0 (
    echo    ERROR: PostgreSQL is NOT running on port 5432!
    echo.
    echo    Please:
    echo    1. Open PostgreSQL Desktop (pgAdmin)
    echo    2. Start the PostgreSQL server
    echo    3. Run this script again
    echo.
    pause
    exit /b 1
) else (
    echo    OK: PostgreSQL is running on port 5432
)
echo.

echo Step 2: Updating .env file...
powershell -ExecutionPolicy Bypass -File UPDATE_POSTGRESQL_ENV.ps1
if %errorlevel% neq 0 (
    echo    ERROR: Failed to update .env file
    pause
    exit /b 1
)
echo.

echo Step 3: Restarting Docker services...
docker-compose restart web celery celery-beat
if %errorlevel% neq 0 (
    echo    ERROR: Failed to restart services
    pause
    exit /b 1
)
echo    OK: Services restarted
echo.

echo Step 4: Testing PostgreSQL connection...
timeout /t 3 /nobreak >nul
docker-compose exec -T web python manage.py dbshell -c "\q" 2>nul
if %errorlevel% neq 0 (
    echo    WARNING: Could not connect to PostgreSQL
    echo    Please check:
    echo    - PostgreSQL Desktop is running
    echo    - Database 'hms_db' exists
    echo    - Credentials in .env are correct
    echo.
) else (
    echo    OK: PostgreSQL connection successful!
    echo.
    echo Step 5: Running migrations...
    docker-compose exec web python manage.py migrate
)
echo.

echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Access your application: http://localhost:8000
echo.
pause















