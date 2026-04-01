@echo off
echo ========================================
echo Starting HMS Server - Fixed Version
echo ========================================
echo.

REM Check Python
python --version
if errorlevel 1 (
    echo ERROR: Python not found!
    pause
    exit /b 1
)

echo.
echo Checking database connection...
python manage.py check --database default >nul 2>&1
if errorlevel 1 (
    echo WARNING: Database check failed. Continuing anyway...
    echo.
)

echo.
echo ========================================
echo Starting Server on 0.0.0.0:8000
echo ========================================
echo.
echo Server will be accessible at:
echo   - Local: http://127.0.0.1:8000
echo   - Network: http://192.168.0.105:8000
echo.
echo IMPORTANT: Configure firewall first!
echo Right-click allow_port_8000_firewall.bat -^> Run as administrator
echo.
echo ========================================
echo.
echo Starting server...
echo.

python manage.py runserver 0.0.0.0:8000

if errorlevel 1 (
    echo.
    echo ========================================
    echo ERROR: Server failed to start!
    echo ========================================
    echo.
    echo Common issues:
    echo   1. Port 8000 already in use
    echo   2. Database connection failed
    echo   3. Missing dependencies
    echo.
    echo Check the error messages above.
    echo.
    pause
)






