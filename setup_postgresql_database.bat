@echo off
REM Setup PostgreSQL Database for HMS
REM This script creates the HMS database and user

setlocal enabledelayedexpansion

echo ===============================================================================
echo                Setup PostgreSQL Database for HMS
echo ===============================================================================
echo.

REM Check if PostgreSQL is installed
echo Checking PostgreSQL installation...
echo.

set "PSQL_PATH="

REM Check common PostgreSQL installation paths
if exist "C:\Program Files\PostgreSQL\16\bin\psql.exe" (
    set "PSQL_PATH=C:\Program Files\PostgreSQL\16\bin"
) else if exist "C:\Program Files\PostgreSQL\15\bin\psql.exe" (
    set "PSQL_PATH=C:\Program Files\PostgreSQL\15\bin"
) else if exist "C:\Program Files\PostgreSQL\14\bin\psql.exe" (
    set "PSQL_PATH=C:\Program Files\PostgreSQL\14\bin"
) else (
    echo [ERROR] PostgreSQL not found!
    echo.
    echo Please install PostgreSQL first:
    echo 1. Run: install_postgresql.bat
    echo 2. Or download from: https://www.postgresql.org/download/windows/
    echo.
    pause
    exit /b 1
)

echo [SUCCESS] PostgreSQL found at: %PSQL_PATH%
echo.

REM Check if PostgreSQL service is running
sc query postgresql-x64-16 | find "RUNNING" >nul
if %errorlevel% neq 0 (
    echo PostgreSQL service is not running. Attempting to start...
    net start postgresql-x64-16 >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Could not start PostgreSQL service
        echo Please start it manually from Services
        pause
        exit /b 1
    )
    echo [SUCCESS] PostgreSQL service started
)

echo.
echo ===============================================================================
echo                Database Configuration
echo ===============================================================================
echo.
echo We will create:
echo   - Database: hms_test
echo   - User: hms_user
echo   - Password: hms_password_123
echo.
echo You will need to enter the PostgreSQL 'postgres' superuser password
echo (the one you set during PostgreSQL installation)
echo.

REM Create temporary SQL script
set "TEMP_SQL=%TEMP%\hms_setup.sql"

echo -- Create HMS database and user > "%TEMP_SQL%"
echo CREATE DATABASE hms_test; >> "%TEMP_SQL%"
echo CREATE USER hms_user WITH PASSWORD 'hms_password_123'; >> "%TEMP_SQL%"
echo GRANT ALL PRIVILEGES ON DATABASE hms_test TO hms_user; >> "%TEMP_SQL%"
echo \c hms_test >> "%TEMP_SQL%"
echo GRANT ALL ON SCHEMA public TO hms_user; >> "%TEMP_SQL%"
echo ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO hms_user; >> "%TEMP_SQL%"
echo ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO hms_user; >> "%TEMP_SQL%"

echo Running database setup...
echo.

REM Run the SQL script
cd /d "%PSQL_PATH%"
psql.exe -U postgres -f "%TEMP_SQL%"

if errorlevel 1 (
    echo.
    echo [ERROR] Database setup failed!
    echo.
    echo Common issues:
    echo 1. Wrong postgres password
    echo 2. Database already exists
    echo.
    echo To reset:
    echo   psql -U postgres
    echo   DROP DATABASE IF EXISTS hms_test;
    echo   DROP USER IF EXISTS hms_user;
    echo.
    del "%TEMP_SQL%" 2>nul
    pause
    exit /b 1
)

REM Clean up
del "%TEMP_SQL%" 2>nul

echo.
echo ===============================================================================
echo [SUCCESS] Database Setup Complete!
echo ===============================================================================
echo.
echo Database Details:
echo   Host: localhost (127.0.0.1)
echo   Port: 5432
echo   Database: hms_test
echo   User: hms_user
echo   Password: hms_password_123
echo.
echo Connection String:
echo   DATABASE_URL=postgresql://hms_user:hms_password_123@localhost:5432/hms_test
echo.
echo ===============================================================================
echo                Next Steps
echo ===============================================================================
echo.
echo 1. Run: install_requirements.bat (to install psycopg2)
echo.
echo 2. Update your .env file with:
echo    DATABASE_URL=postgresql://hms_user:hms_password_123@localhost:5432/hms_test
echo.
echo 3. Test connection:
echo    python test_db_connection.py
echo.
echo 4. Run migrations:
echo    python manage.py migrate
echo.
echo 5. Create superuser:
echo    python manage.py createsuperuser
echo.
echo 6. Start server:
echo    python manage.py runserver
echo.
echo ===============================================================================
echo.
pause

