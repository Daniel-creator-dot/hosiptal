@echo off
setlocal enabledelayedexpansion
echo ========================================
echo Starting HMS Server - Quick Start
echo ========================================
echo.

REM Try to activate venv if it exists
if exist .venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo No virtual environment found - using system Python
)

echo.
echo Starting Django development server...
echo.
echo Server will be available at:
echo   http://127.0.0.1:8000
echo   http://localhost:8000
echo.
echo Getting your WiFi IP address for network access...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i /c:"IPv4" ^| findstr /v /i "192.168.169 172.17 172.18 172.19 172.20 172.21 172.22 172.23 172.24 172.25 172.26 172.27 172.28 172.29 172.30 172.31"') do (
    set WIFI_IP=%%a
    set WIFI_IP=!WIFI_IP: =!
    if "!WIFI_IP!" neq "" (
        echo   http://!WIFI_IP!:8000 (WiFi access)
        goto :ip_found
    )
)
:ip_found
echo.
echo Press Ctrl+C to stop the server
echo.
echo ========================================
echo.

python manage.py runserver 0.0.0.0:8000

pause
