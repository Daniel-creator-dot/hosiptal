@echo off
setlocal enabledelayedexpansion
REM ========================================
REM HMS Docker Start Script
REM PostgreSQL Desktop + Docker Desktop
REM ========================================
echo.
echo ========================================
echo   HMS DOCKER START
echo   PostgreSQL Desktop + Docker Desktop
echo ========================================
echo.

REM Check if Docker is running
echo [1/5] Checking Docker Desktop...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Docker Desktop is not running!
    echo    Please start Docker Desktop and try again.
    echo.
    pause
    exit /b 1
)
echo    ✅ Docker Desktop is running
echo.

REM Check if .env file exists
echo [2/5] Checking .env file...
if not exist .env (
    echo    ⚠️  .env file not found!
    echo    Creating .env from template...
    if exist env.local.example (
        copy env.local.example .env >nul
        echo    ✅ Created .env file
        echo.
        echo    ⚠️  IMPORTANT: Edit .env and update DATABASE_URL!
        echo    Example: DATABASE_URL=postgresql://postgres:postgres@host.docker.internal:5432/hms_db
        echo.
        pause
    ) else (
        echo    ❌ ERROR: env.local.example not found!
        pause
        exit /b 1
    )
) else (
    echo    ✅ .env file exists
)
echo.

REM Detect local network IP for CSRF
echo [3/5] Detecting network IP...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    set IP_LINE=%%a
    set IP_LINE=!IP_LINE: =!
    for /f "tokens=1" %%b in ("!IP_LINE!") do (
        set LOCAL_IP=%%b
        echo !LOCAL_IP! | findstr /r "^192\.168\." >nul
        if !errorlevel! equ 0 (
            goto :found_ip
        )
        echo !LOCAL_IP! | findstr /r "^10\." >nul
        if !errorlevel! equ 0 (
            goto :found_ip
        )
    )
)
:found_ip
if "%LOCAL_IP%"=="" (
    set LOCAL_IP=192.168.1.100
    echo    ⚠️  Using default IP: %LOCAL_IP%
) else (
    echo    ✅ Detected IP: %LOCAL_IP%
)
echo.

REM Build Docker images
echo [4/5] Building Docker images...
echo    This may take a few minutes on first run...
docker-compose build
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Failed to build Docker images
    echo    Check the error messages above
    pause
    exit /b 1
)
echo    ✅ Build complete
echo.

REM Start services
echo [5/5] Starting services...
docker-compose up -d
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Failed to start services
    echo    Check the error messages above
    pause
    exit /b 1
)
echo    ✅ Services starting...
echo.

REM Wait a moment for services to initialize
timeout /t 3 /nobreak >nul

echo ========================================
echo   ✅ SETUP COMPLETE!
echo ========================================
echo.
echo 📋 Next Steps:
echo.
echo 1. Run database migrations:
echo    docker-compose exec web python manage.py migrate
echo.
echo 2. Create superuser (optional):
echo    docker-compose exec web python manage.py createsuperuser
echo.
echo 3. View logs:
echo    docker-compose logs -f web
echo.
echo 🌐 Access your application:
echo    - Local: http://localhost:8000
echo    - Network: http://%LOCAL_IP%:8000
echo.
echo 🛑 To stop services: docker-compose down
echo.
pause






