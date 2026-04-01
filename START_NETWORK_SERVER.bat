@echo off
setlocal enabledelayedexpansion
echo ========================================
echo Starting HMS Server - Network Access
echo ========================================
echo.

REM Check if port 8000 is already in use
netstat -an | findstr ":8000" >nul
if %errorlevel% equ 0 (
    echo WARNING: Port 8000 is already in use!
    echo Please stop the existing server first (Ctrl+C in that window)
    echo.
    pause
    exit /b 1
)

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
echo Checking firewall rules for port 8000...
netsh advfirewall firewall show rule name="HMS Port 8000" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ========================================
    echo FIREWALL CONFIGURATION NEEDED
    echo ========================================
    echo.
    echo Port 8000 needs to be allowed through Windows Firewall.
    echo.
    echo Option 1: Run this script as Administrator
    echo   Right-click this file -> Run as administrator
    echo.
    echo Option 2: Run the firewall script as Administrator
    echo   Right-click: allow_port_8000_firewall.bat -> Run as administrator
    echo.
    echo Option 3: Manual configuration
    echo   1. Open Windows Defender Firewall
    echo   2. Click "Advanced Settings"
    echo   3. Click "Inbound Rules" -> "New Rule"
    echo   4. Select "Port" -> Next
    echo   5. Select "TCP" -> Enter "8000" -> Next
    echo   6. Select "Allow the connection" -> Next
    echo   7. Check all profiles -> Next
    echo   8. Name: "HMS Port 8000" -> Finish
    echo.
    echo Press any key to continue anyway (server may not be accessible from network)...
    pause >nul
)

echo.
echo ========================================
echo Starting Django Development Server
echo ========================================
echo.
echo Server will be available at:
echo   - Local: http://127.0.0.1:8000
echo   - Local: http://localhost:8000
echo.

REM Get current IP addresses
echo Detecting network IP addresses...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i /c:"IPv4"') do (
    set IP=%%a
    set IP=!IP: =!
    if "!IP!" neq "" (
        echo   - Network: http://!IP!:8000
    )
)
echo.

echo Your IP 192.168.0.105 should be accessible at:
echo   http://192.168.0.105:8000
echo.
echo ========================================
echo.
echo Starting server on 0.0.0.0:8000 (all network interfaces)...
echo.
echo Press Ctrl+C to stop the server
echo.
echo ========================================
echo.

python manage.py runserver 0.0.0.0:8000

pause






