@echo off
REM ================================================================
REM Docker Production Start Script (Windows)
REM Use this to prepare files before copying to Docker server
REM ================================================================

echo ================================================================
echo   Docker Production Setup - File Preparation
echo ================================================================
echo.

REM Check if Docker is installed locally (optional)
where docker >nul 2>&1
if errorlevel 1 (
    echo [INFO] Docker not found locally - this is OK if deploying to remote server
    echo.
) else (
    echo [OK] Docker found locally
    echo.
)

echo This script will help you prepare files for Docker deployment.
echo.
echo STEP 1: Verify Required Files
echo ----------------------------------------
if exist docker-compose.yml (
    echo [OK] docker-compose.yml found
) else (
    echo [ERROR] docker-compose.yml not found!
    pause
    exit /b 1
)

if exist Dockerfile (
    echo [OK] Dockerfile found
) else (
    echo [ERROR] Dockerfile not found!
    pause
    exit /b 1
)

if exist requirements.txt (
    echo [OK] requirements.txt found
) else (
    echo [ERROR] requirements.txt not found!
    pause
    exit /b 1
)

if exist .env (
    echo [OK] .env file found
) else (
    echo [WARNING] .env file not found - you'll need to create it on the server
)

echo.
echo STEP 2: Files Ready for Docker Deployment
echo ----------------------------------------
echo.
echo Your project is ready to copy to Docker server!
echo.
echo Next steps:
echo 1. Copy this entire folder to your Docker server
echo 2. On Docker server, run:
echo    cd /path/to/chm
echo    docker-compose up -d
echo 3. Run migrations:
echo    docker-compose exec web python manage.py migrate
echo 4. Create superuser:
echo    docker-compose exec web python manage.py createsuperuser
echo.
echo See DOCKER_PRODUCTION_SETUP.md for complete guide
echo.
pause



