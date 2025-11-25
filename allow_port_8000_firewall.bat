@echo off
REM Script to allow port 8000 through Windows Firewall
REM Run as Administrator

echo ========================================
echo Configuring Windows Firewall for HMS
echo ========================================
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script must be run as Administrator!
    echo.
    echo Please:
    echo 1. Right-click this file
    echo 2. Select "Run as administrator"
    echo 3. Click "Yes" when prompted
    echo.
    pause
    exit /b 1
)

echo Adding firewall rule for port 8000...
netsh advfirewall firewall delete rule name="HMS Docker Port 8000" >nul 2>&1
netsh advfirewall firewall add rule name="HMS Docker Port 8000" dir=in action=allow protocol=TCP localport=8000

if %errorlevel% equ 0 (
    echo ✅ Firewall rule added successfully!
) else (
    echo ❌ Failed to add firewall rule
    pause
    exit /b 1
)

echo.
echo Verifying firewall rule...
netsh advfirewall firewall show rule name="HMS Docker Port 8000"
echo.

echo ========================================
echo ✅ Firewall Configuration Complete!
echo ========================================
echo.
echo Port 8000 is now open for network access.
echo.
echo Your HMS is accessible at:
echo    Local:  http://localhost:8000
echo    Network: http://192.168.0.100:8000
echo.
echo Test from another device on your network!
echo.
pause

