@echo off
REM Database Import Utility - Windows Batch File
REM Double-click this file to import the legacy database

echo ===============================================================
echo     HOSPITAL MANAGEMENT SYSTEM - DATABASE IMPORT
echo ===============================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python and try again.
    pause
    exit /b 1
)

echo Python found: 
python --version
echo.

REM Check if database backup exists
if exist "db.sqlite3" (
    echo Database file found: db.sqlite3
    echo.
    echo Creating backup...
    copy db.sqlite3 db.sqlite3.backup >nul 2>&1
    if errorlevel 0 (
        echo Backup created: db.sqlite3.backup
    ) else (
        echo WARNING: Could not create backup
    )
) else (
    echo No existing database found. Will create new one.
)

echo.
echo ===============================================================
echo Starting import process...
echo ===============================================================
echo.

REM Run the import script
python import_database.py

echo.
echo ===============================================================
echo Import process completed!
echo ===============================================================
echo.
echo Next steps:
echo 1. Run: python manage.py migrate
echo 2. Run: python manage.py runserver
echo 3. Visit: http://127.0.0.1:8000/admin/
echo.

pause




















