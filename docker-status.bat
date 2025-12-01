@echo off
REM ========================================
REM 🐳 DOCKER STATUS CHECK
REM ========================================
echo.
echo ========================================
echo   🐳 HMS DOCKER STATUS
echo ========================================
echo.

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker Desktop is not running!
    echo    Please start Docker Desktop first.
    echo.
    pause
    exit /b 1
)

echo ✅ Docker is running
echo.

REM Show running containers
echo 📦 Running Containers:
echo.
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo.

REM Check if web container is running
docker ps --format "{{.Names}}" | findstr /i "web" >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️  Web container is not running!
    echo    Starting containers...
    docker-compose up -d
    echo    Waiting for services to start...
    timeout /t 10 /nobreak >nul
    echo.
)

REM Test health endpoint
echo 🔍 Testing application...
curl -s http://localhost:8000/health/ >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Application is accessible!
    echo.
    echo 🌐 Access your application:
    echo    http://localhost:8000
    echo    http://localhost:8000/admin
    echo    http://localhost:8000/hms/
    echo    http://localhost:8000/health/
    echo.
) else (
    echo ⚠️  Application may still be starting...
    echo    Wait a few seconds and try again.
    echo.
)

echo 📋 Useful Commands:
echo    View logs: docker-compose logs -f web
echo    Stop: docker-compose down
echo    Restart: docker-compose restart web
echo    Status: docker ps
echo.
pause

