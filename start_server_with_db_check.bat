@echo off
echo ========================================
echo Django Server Startup Script
echo ========================================
echo.

cd /d d:\chm

echo Checking PostgreSQL connection...
python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings'); import django; django.setup(); from django.db import connection; connection.ensure_connection(); print('✓ Database connection OK')" 2>nul
if %errorlevel% neq 0 (
    echo.
    echo ⚠️  WARNING: Cannot connect to PostgreSQL database!
    echo.
    echo Please ensure PostgreSQL is running:
    echo   1. Check if PostgreSQL service is running
    echo   2. Or start PostgreSQL Docker container
    echo   3. Or check your DATABASE_URL in .env file
    echo.
    echo Attempting to start server anyway...
    echo (Server will fail if database is not available)
    echo.
    timeout /t 3 /nobreak >nul
)

echo.
echo Starting Django Server on 0.0.0.0:8000...
echo Press Ctrl+C to stop the server
echo.
python manage.py runserver 0.0.0.0:8000

pause
