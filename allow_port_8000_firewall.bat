@echo off
echo ========================================
echo Configuring Windows Firewall for HMS
echo ========================================
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script must be run as Administrator!
    echo.
    echo Right-click this file and select "Run as administrator"
    echo.
    pause
    exit /b 1
)

echo Adding firewall rule for port 8000...
echo.

REM Delete existing rule if it exists
netsh advfirewall firewall delete rule name="HMS Port 8000" >nul 2>&1

REM Add new rule
netsh advfirewall firewall add rule name="HMS Port 8000" dir=in action=allow protocol=TCP localport=8000

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo SUCCESS!
    echo ========================================
    echo.
    echo Firewall rule added successfully!
    echo Port 8000 is now allowed through Windows Firewall.
    echo.
    echo You can now start the server and access it from:
    echo   - http://192.168.0.105:8000 (from other devices)
    echo   - http://127.0.0.1:8000 (local)
    echo.
) else (
    echo.
    echo ERROR: Failed to add firewall rule!
    echo Please try manual configuration (see START_NETWORK_SERVER.bat)
    echo.
)

pause
