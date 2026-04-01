@echo off
REM ================================================================
REM Fix PostgreSQL Authentication for HMS
REM ================================================================

echo ================================================================
echo   Fix PostgreSQL Authentication
echo ================================================================
echo.

REM Find PostgreSQL psql.exe
set "PSQL_PATH="
if exist "C:\Program Files\PostgreSQL\16\bin\psql.exe" (
    set "PSQL_PATH=C:\Program Files\PostgreSQL\16\bin\psql.exe"
) else if exist "C:\Program Files\PostgreSQL\15\bin\psql.exe" (
    set "PSQL_PATH=C:\Program Files\PostgreSQL\15\bin\psql.exe"
) else if exist "C:\Program Files\PostgreSQL\14\bin\psql.exe" (
    set "PSQL_PATH=C:\Program Files\PostgreSQL\14\bin\psql.exe"
) else (
    REM Try to find psql in PATH
    where psql >nul 2>&1
    if not errorlevel 1 (
        set "PSQL_PATH=psql"
    )
)

if "%PSQL_PATH%"=="" (
    echo [ERROR] PostgreSQL psql command not found!
    echo.
    echo Please ensure PostgreSQL is installed.
    echo.
    echo Common PostgreSQL installation paths:
    echo   C:\Program Files\PostgreSQL\15\bin\psql.exe
    echo   C:\Program Files\PostgreSQL\16\bin\psql.exe
    echo.
    echo Alternative: Use pgAdmin GUI method (FIX_POSTGRESQL_AUTH_SIMPLE.bat)
    echo.
    pause
    exit /b 1
)

echo Found PostgreSQL at: %PSQL_PATH%
echo.

echo Step 1: Testing PostgreSQL connection as 'postgres' user...
echo.
echo You will be prompted for the PostgreSQL 'postgres' user password.
echo (This is the password you set during PostgreSQL installation)
echo.

REM Try to connect and create/fix user and database
echo Creating SQL script...
set "TEMP_SQL=%TEMP%\hms_fix_auth.sql"

(
    echo -- Fix HMS PostgreSQL Authentication
    echo -- Create user if not exists
    echo DO $$
    echo BEGIN
    echo     IF NOT EXISTS ^(SELECT FROM pg_catalog.pg_user WHERE usename = 'hms_user'^) THEN
    echo         CREATE USER hms_user WITH PASSWORD 'hms_password';
    echo     ELSE
    echo         ALTER USER hms_user WITH PASSWORD 'hms_password';
    echo     END IF;
    echo END
    echo $$;
    echo.
    echo -- Create database if not exists
    echo SELECT 'CREATE DATABASE hms_db'
    echo WHERE NOT EXISTS ^(SELECT FROM pg_database WHERE datname = 'hms_db'^)\gexec
    echo.
    echo -- Grant privileges
    echo GRANT ALL PRIVILEGES ON DATABASE hms_db TO hms_user;
    echo.
    echo -- Connect to hms_db and grant schema privileges
    echo \c hms_db
    echo GRANT ALL ON SCHEMA public TO hms_user;
    echo ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO hms_user;
    echo ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO hms_user;
    echo.
    echo -- Set user properties
    echo \c postgres
    echo ALTER ROLE hms_user SET client_encoding TO 'utf8';
    echo ALTER ROLE hms_user SET default_transaction_isolation TO 'read committed';
    echo ALTER ROLE hms_user SET timezone TO 'UTC';
) > "%TEMP_SQL%"

echo Running PostgreSQL setup...
echo.

REM Try to run psql
"%PSQL_PATH%" -U postgres -f "%TEMP_SQL%"

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to connect to PostgreSQL!
    echo.
    echo Common issues:
    echo 1. PostgreSQL service is not running
    echo    - Check Services: services.msc
    echo    - Look for "postgresql" service and start it
    echo.
    echo 2. Wrong postgres password
    echo    - Try the password you set during PostgreSQL installation
    echo    - Or check pgAdmin to see what password works
    echo.
    echo 3. PostgreSQL not installed
    echo    - Download from: https://www.postgresql.org/download/windows/
    echo.
    echo Alternative: Use pgAdmin GUI
    echo 1. Open pgAdmin
    echo 2. Connect to PostgreSQL server
    echo 3. Run the SQL commands manually (see below)
    echo.
    echo SQL Commands to run in pgAdmin:
    echo ----------------------------------------
    type "%TEMP_SQL%"
    echo ----------------------------------------
    echo.
    del "%TEMP_SQL%" 2>nul
    pause
    exit /b 1
)

REM Clean up
del "%TEMP_SQL%" 2>nul

echo.
echo ================================================================
echo [SUCCESS] PostgreSQL Authentication Fixed!
echo ================================================================
echo.
echo Database Details:
echo   Host: localhost
echo   Port: 5432
echo   Database: hms_db
echo   User: hms_user
echo   Password: hms_password
echo.
echo Your .env file should have:
echo   DATABASE_URL=postgresql://hms_user:hms_password@localhost:5432/hms_db
echo.
echo Next Steps:
echo 1. Verify .env file has correct DATABASE_URL
echo 2. Run: python manage.py migrate
echo 3. Start your Django server
echo.
echo ================================================================
pause

