@echo off
REM Quick start script for Docker Desktop + PostgreSQL Desktop setup
echo ========================================
echo HMS Docker Setup
echo ========================================
echo.

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker Desktop is not running!
    echo Please start Docker Desktop and try again.
    pause
    exit /b 1
)

echo [1/4] Checking Docker Desktop... OK
echo.

REM Check if .env file exists
if not exist .env (
    echo [2/4] .env file not found!
    echo.
    echo Creating .env from template...
    copy env.local.example .env
    echo.
    echo IMPORTANT: Please edit .env and update DATABASE_URL with your PostgreSQL Desktop credentials!
    echo Example: DATABASE_URL=postgresql://postgres:postgres@host.docker.internal:5432/hms_db
    echo.
    pause
)

echo [2/4] Checking .env file... OK
echo.

echo [3/4] Building Docker images...
docker-compose build
if %errorlevel% neq 0 (
    echo ERROR: Failed to build Docker images
    pause
    exit /b 1
)

echo.
echo [4/4] Starting services...
docker-compose up -d
if %errorlevel% neq 0 (
    echo ERROR: Failed to start services
    pause
    exit /b 1
)

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Services are starting up. Wait a few seconds, then:
echo.
echo 1. Run migrations:
echo    docker-compose exec web python manage.py migrate
echo.
echo 2. Create superuser (optional):
echo    docker-compose exec web python manage.py createsuperuser
echo.
echo 3. View logs:
echo    docker-compose logs -f web
echo.
echo 4. Access application:
echo    http://localhost:8000
echo.
echo To stop services: docker-compose down
echo.
pause















