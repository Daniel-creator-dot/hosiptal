@echo off
REM PostgreSQL Installation Helper for HMS
REM This script will download and help you install PostgreSQL on Windows

echo ===============================================================================
echo                  PostgreSQL Installation for HMS
echo ===============================================================================
echo.
echo This will help you download and install PostgreSQL on your Windows machine.
echo.
echo Installation Steps:
echo 1. We'll open the download page for PostgreSQL
echo 2. Download the installer for Windows
echo 3. Run the installer
echo 4. Configure PostgreSQL for HMS
echo.
echo Press any key to open the PostgreSQL download page...
pause >nul

echo.
echo Opening PostgreSQL download page...
start https://www.enterprisedb.com/downloads/postgres-postgresql-downloads

echo.
echo ===============================================================================
echo INSTALLATION INSTRUCTIONS:
echo ===============================================================================
echo.
echo 1. Download PostgreSQL 16 for Windows (latest version)
echo.
echo 2. Run the downloaded .exe file
echo.
echo 3. During installation:
echo    - Installation Directory: Accept default (C:\Program Files\PostgreSQL\16)
echo    - Select Components: Install ALL (Server, pgAdmin, Command Line Tools)
echo    - Data Directory: Accept default
echo    - Password: Set a password for 'postgres' user
echo      IMPORTANT: Remember this password! (e.g., "admin123")
echo    - Port: 5432 (default)
echo    - Locale: Default locale
echo.
echo 4. After installation completes:
echo    - Run: setup_postgresql_database.bat
echo.
echo ===============================================================================
echo.
echo Waiting for you to complete installation...
echo Press any key after PostgreSQL installation is complete...
pause >nul

echo.
echo Checking if PostgreSQL is installed...
timeout /t 2 /nobreak >nul

sc query postgresql-x64-16 >nul 2>&1
if %errorlevel% equ 0 (
    echo [SUCCESS] PostgreSQL service found!
    echo.
    echo Next step: Run setup_postgresql_database.bat to configure the database
    echo.
) else (
    echo [INFO] PostgreSQL service not detected yet.
    echo.
    echo If you just completed installation:
    echo 1. Restart this command prompt
    echo 2. Run: setup_postgresql_database.bat
    echo.
)

echo Press any key to exit...
pause >nul

