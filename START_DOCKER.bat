@echo off
REM ========================================
REM START DOCKER - DOUBLE CLICK THIS FILE!
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
    echo    ERROR: Docker Desktop is not running!
    echo    Please start Docker Desktop and try again.
    echo.
    pause
    exit /b 1
)
echo    OK: Docker Desktop is running
echo.

REM Check if .env file exists
echo [2/5] Checking .env file...
if not exist .env (
    echo    WARNING: .env file not found!
    echo    Creating .env from template...
    if exist env.local.example (
        copy env.local.example .env >nul
        echo    OK: Created .env file
        echo.
        echo    IMPORTANT: Edit .env and update DATABASE_URL!
        echo    Example: DATABASE_URL=postgresql://postgres:postgres@host.docker.internal:5432/hms_db
        echo.
        pause
    ) else (
        echo    ERROR: env.local.example not found!
        pause
        exit /b 1
    )
) else (
    echo    OK: .env file exists
)
echo.

REM Build Docker images
echo [3/5] Building Docker images...
echo    This may take a few minutes on first run...
docker-compose build
if %errorlevel% neq 0 (
    echo    ERROR: Failed to build Docker images
    pause
    exit /b 1
)
echo    OK: Build complete
echo.

REM Start services
echo [4/5] Starting services...
docker-compose up -d
if %errorlevel% neq 0 (
    echo    ERROR: Failed to start services
    pause
    exit /b 1
)
echo    OK: Services starting...
echo.

REM Wait a moment
timeout /t 3 /nobreak >nul

echo [5/5] Running database migrations...
docker-compose exec -T web python manage.py migrate 2>nul
if %errorlevel% neq 0 (
    echo    WARNING: Migrations will run on first access
) else (
    echo    OK: Migrations complete
)
echo.

echo ========================================
echo   SETUP COMPLETE!
echo ========================================
echo.
echo Access your application:
echo    http://localhost:8000
echo.
echo Useful Commands:
echo    View logs: docker-compose logs -f web
echo    Stop: docker-compose down
echo    Restart: docker-compose restart
echo.
pause















