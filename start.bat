@echo off
echo Starting Hospital Management System...

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Docker is not running. Please start Docker and try again.
    pause
    exit /b 1
)

REM Build and start services
echo Building and starting services...
docker-compose up -d --build

REM Wait for services to be ready
echo Waiting for services to be ready...
timeout /t 10 /nobreak >nul

REM Run migrations
echo Running database migrations...
docker-compose exec web python manage.py migrate

REM Initialize system
echo Initializing system...
docker-compose exec web python manage.py init_hms

REM Collect static files
echo Collecting static files...
docker-compose exec web python manage.py collectstatic --noinput

echo.
echo ✅ HMS is now running!
echo.
echo 🌐 Web Interface: http://localhost:8000
echo 🔧 Admin Panel: http://localhost:8000/admin
echo ❤️  Health Check: http://localhost:8000/health/
echo 📊 Metrics: http://localhost:8000/prometheus/
echo 🗄️  MinIO Console: http://localhost:9001
echo.
echo Default Admin Credentials:
echo Username: admin
echo Password: admin123
echo.
echo To stop the services, run: docker-compose down
pause
