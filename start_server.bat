@echo off
echo ========================================
echo STARTING HMS SERVER
echo ========================================
echo.

echo Checking services...
docker-compose ps
echo.

echo Starting all services...
docker-compose up -d
echo.

echo Waiting for services to start...
timeout /t 5 /nobreak >nul
echo.

echo ========================================
echo SERVER STATUS
echo ========================================
echo.
docker-compose ps
echo.

echo ========================================
echo ACCESS YOUR APPLICATION
echo ========================================
echo.
echo Open your browser and go to:
echo    http://localhost:8000
echo.
echo If you see database errors, you need to:
echo    1. Open pgAdmin (PostgreSQL Desktop)
echo    2. Set postgres user password to match .env file
echo    3. Create database 'hms_db'
echo    4. Run: docker-compose exec web python manage.py migrate
echo.
echo View logs: docker-compose logs -f web
echo Stop server: docker-compose down
echo.

pause
