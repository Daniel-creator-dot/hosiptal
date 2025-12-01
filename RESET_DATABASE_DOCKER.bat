@echo off
REM Docker-based Database Reset Script for Windows
REM This will reset the database using Docker Compose

echo ====================================================================
echo DOCKER DATABASE RESET
echo ====================================================================
echo.
echo WARNING: This will DELETE ALL DATA in the database!
echo.
echo This script will:
echo   1. Stop all Docker services
echo   2. Remove the database volume
echo   3. Start services fresh
echo   4. Run all Django migrations
echo.
pause

REM Check if Docker is available
docker --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not installed or not in PATH
    echo Please install Docker Desktop and try again
    pause
    exit /b 1
)

REM Check if docker-compose is available
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: docker-compose is not installed or not in PATH
    pause
    exit /b 1
)

REM Run the Python script
echo.
echo Running Docker database reset script...
python reset_database_docker.py

if errorlevel 1 (
    echo.
    echo ERROR: Database reset failed!
    pause
    exit /b 1
)

echo.
echo ====================================================================
echo Database reset complete!
echo ====================================================================
echo.
echo Next steps:
echo   1. Create a superuser: docker-compose exec web python manage.py createsuperuser
echo   2. Access the application: http://localhost:8000
echo.
pause

