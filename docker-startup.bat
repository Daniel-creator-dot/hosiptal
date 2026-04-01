@echo off
REM Docker Startup Script for HMS (Windows)
REM This script ensures all structures are updated and services are ready

echo 🚀 Starting HMS Docker Services...

REM Start all services
docker-compose up -d --remove-orphans

REM Wait for services to be healthy
echo ⏳ Waiting for services to be healthy...
timeout /t 15 /nobreak >nul

REM Run migrations
echo 📊 Running database migrations...
docker-compose exec -T web python manage.py migrate --noinput

REM Setup RBAC roles
echo 👥 Setting up RBAC roles...
docker-compose exec -T web python manage.py setup_rbac

REM Collect static files
echo 📦 Collecting static files...
docker-compose exec -T web python manage.py collectstatic --noinput

echo ✅ HMS is ready!
echo 🌐 Access the application at: http://localhost:8000

pause











