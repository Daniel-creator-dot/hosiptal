@echo off
setlocal enabledelayedexpansion
echo ========================================
echo COMPLETE HMS SETUP
echo PostgreSQL Desktop + Docker Desktop
echo ========================================
echo.

echo [1/6] Checking Docker Desktop...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo    ERROR: Docker Desktop is not running!
    echo    Please start Docker Desktop and try again.
    pause
    exit /b 1
)
echo    OK: Docker Desktop is running
echo.

echo [2/6] Checking PostgreSQL Desktop...
netstat -an | findstr ":5432" >nul
if %errorlevel% neq 0 (
    echo    WARNING: PostgreSQL may not be running on port 5432
    echo    Please start PostgreSQL Desktop (pgAdmin)
    echo    The setup will continue, but you may need to start PostgreSQL manually
) else (
    echo    OK: PostgreSQL is running on port 5432
)
echo.

echo [3/6] Updating .env file...
if not exist .env (
    if exist env.local.example (
        copy env.local.example .env >nul
        echo    Created .env from template
    )
)

REM Update DATABASE_URL in .env
powershell -Command "$content = Get-Content .env -Raw; $content = $content -replace 'DATABASE_URL=.*', 'DATABASE_URL=postgresql://postgres:postgres@host.docker.internal:5432/hms_db'; $content | Set-Content .env -NoNewline"
echo    Updated DATABASE_URL
echo.

echo [4/6] Building and starting Docker services...
docker-compose down >nul 2>&1
docker-compose build --quiet
if %errorlevel% neq 0 (
    echo    ERROR: Failed to build Docker images
    pause
    exit /b 1
)
docker-compose up -d
if %errorlevel% neq 0 (
    echo    ERROR: Failed to start services
    pause
    exit /b 1
)
echo    OK: Services started
echo.

echo [5/6] Waiting for services to be ready...
timeout /t 10 /nobreak >nul
echo.

echo [6/6] Setting up database...
echo    Attempting to create database and run migrations...
docker-compose exec -T web python create_postgresql_db.py 2>nul
docker-compose exec web python manage.py migrate 2>nul
if %errorlevel% equ 0 (
    echo    OK: Database setup complete!
) else (
    echo    WARNING: Database setup may need manual intervention
    echo    See POSTGRESQL_FINAL_SETUP.txt for instructions
)
echo.

echo ========================================
echo SETUP COMPLETE!
echo ========================================
echo.
echo Your application should be running at:
echo    http://localhost:8000
echo.
echo If you see errors, check:
echo    1. PostgreSQL Desktop is running
echo    2. Password in .env matches PostgreSQL password
echo    3. Database 'hms_db' exists in PostgreSQL
echo.
echo View logs: docker-compose logs -f web
echo.
pause















