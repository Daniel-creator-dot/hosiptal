@echo off
echo ========================================
echo Starting HMS Server - LOCAL MODE
echo ========================================
echo.

echo Checking Python...
python --version
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Please install Python or fix virtual environment
    pause
    exit /b 1
)
echo.

echo Checking Django...
python -c "import django; print('Django version:', django.get_version())" 2>nul
if errorlevel 1 (
    echo WARNING: Django not found in current environment
    echo Attempting to continue anyway...
    echo.
)

echo.
echo ========================================
echo Starting Django Development Server
echo ========================================
echo.
echo Server will be available at:
echo   http://127.0.0.1:8000
echo   http://localhost:8000
echo.
echo Getting your WiFi IP address for network access...
setlocal enabledelayedexpansion
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i /c:"IPv4"') do (
    set WIFI_IP=%%a
    set WIFI_IP=!WIFI_IP: =!
    if "!WIFI_IP!" neq "" (
        echo   http://!WIFI_IP!:8000 (WiFi access)
        goto :ip_found
    )
)
:ip_found
endlocal
echo.
echo To test the new payer selection feature:
echo   http://127.0.0.1:8000/hms/patients/create/
echo.
echo Press Ctrl+C to stop the server
echo.
echo ========================================
echo.

python manage.py runserver 0.0.0.0:8000

pause

