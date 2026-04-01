@echo off
REM Docker Startup Verification Script for Windows
REM This script verifies that all required environment variables and configurations are in place

echo 🔍 Checking Docker configuration...

REM Check if .env file exists
if not exist .env (
    echo ❌ ERROR: .env file not found!
    echo 📝 Creating .env file from env.example...
    if exist env.example (
        copy env.example .env >nul
        echo ✅ Created .env file. Please update it with your configuration.
    ) else (
        echo ❌ ERROR: env.example not found. Cannot create .env file.
        exit /b 1
    )
)

REM Check for required environment variables
echo 🔍 Checking required environment variables...

findstr /C:"DATABASE_URL=" .env >nul 2>&1
if errorlevel 1 (
    echo ⚠️  WARNING: DATABASE_URL not found in .env file
    echo 📝 Please add DATABASE_URL to your .env file
    echo    For Docker: DATABASE_URL=postgresql://hms_user:hms_password@localhost:5432/hms_db
    echo    ^(This will be auto-overridden by docker-compose.yml^)
)

findstr /C:"SECRET_KEY=" .env >nul 2>&1
if errorlevel 1 (
    echo ⚠️  WARNING: SECRET_KEY not found in .env file
    echo 📝 Please add SECRET_KEY to your .env file
)

REM Check docker-compose.yml
if not exist docker-compose.yml (
    echo ❌ ERROR: docker-compose.yml not found!
    exit /b 1
)

echo ✅ Docker configuration files found
echo.
echo 🚀 Ready to start Docker services!
echo.
echo To start all services:
echo   docker-compose up -d
echo.
echo To view logs:
echo   docker-compose logs -f
echo.
echo To stop services:
echo   docker-compose down
echo.
echo To restart services:
echo   docker-compose restart














