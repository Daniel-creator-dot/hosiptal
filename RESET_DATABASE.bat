@echo off
REM Complete Database Reset Script for Windows
REM This will drop all databases and create a fresh PostgreSQL database

echo ====================================================================
echo COMPLETE DATABASE RESET
echo ====================================================================
echo.
echo WARNING: This will DELETE ALL DATA in the database!
echo.
echo This script will:
echo   1. Drop all existing PostgreSQL databases
echo   2. Create a fresh PostgreSQL database
echo   3. Run all Django migrations
echo   4. Update .env file with PostgreSQL configuration
echo.
pause

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python and try again
    pause
    exit /b 1
)

REM Check if psycopg2 is installed
python -c "import psycopg2" >nul 2>&1
if errorlevel 1 (
    echo ERROR: psycopg2 is not installed
    echo Installing psycopg2-binary...
    pip install psycopg2-binary
    if errorlevel 1 (
        echo ERROR: Failed to install psycopg2-binary
        pause
        exit /b 1
    )
)

REM Set default database configuration (can be overridden via environment variables)
if "%DB_HOST%"=="" set DB_HOST=localhost
if "%DB_PORT%"=="" set DB_PORT=5432
if "%DB_USER%"=="" set DB_USER=postgres
if "%DB_PASSWORD%"=="" set DB_PASSWORD=postgres
if "%TARGET_DB%"=="" set TARGET_DB=hms_db
if "%TARGET_USER%"=="" set TARGET_USER=hms_user
if "%TARGET_PASSWORD%"=="" set TARGET_PASSWORD=hms_password

echo.
echo Database Configuration:
echo   Host: %DB_HOST%:%DB_PORT%
echo   Admin User: %DB_USER%
echo   Target Database: %TARGET_DB%
echo   Target User: %TARGET_USER%
echo.
echo To use different settings, set environment variables:
echo   set DB_HOST=your_host
echo   set DB_PASSWORD=your_password
echo   etc.
echo.
pause

REM Run the Python script
echo.
echo Running database reset script...
python reset_database_complete.py

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
echo   1. Create a superuser: python manage.py createsuperuser
echo   2. Start the server: python manage.py runserver
echo   3. Or use Docker: docker-compose up -d
echo.
pause

