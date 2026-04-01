@echo off
REM Deploy Drug Accountability System to Docker
REM This script runs the migration and restarts the web service

echo ==========================================
echo Deploying Drug Accountability System
echo ==========================================
echo.

echo Step 1: Checking Docker containers...
docker-compose ps

echo.
echo Step 2: Running database migration...
docker-compose exec web python manage.py migrate hospital 1058_add_drug_accountability_system

if errorlevel 1 (
    echo.
    echo ERROR: Migration failed!
    echo Trying to run all pending migrations...
    docker-compose exec web python manage.py migrate
)

echo.
echo Step 3: Restarting web service to load new code...
docker-compose restart web

echo.
echo ==========================================
echo Deployment Complete!
echo ==========================================
echo.
echo The web service is restarting...
echo Wait a few seconds, then test:
echo   http://192.168.2.216:8000/hms/drug-returns/
echo.
echo To check logs:
echo   docker-compose logs -f web
echo.
pause







