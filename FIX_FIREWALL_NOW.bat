@echo off
echo ========================================
echo Fixing Windows Firewall for WiFi Access
echo ========================================
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ ERROR: This script must be run as Administrator!
    echo.
    echo TO FIX:
    echo 1. Right-click this file
    echo 2. Select "Run as administrator"
    echo 3. Click "Yes" when prompted
    echo.
    pause
    exit /b 1
)

echo ✅ Running as Administrator
echo.

echo [1/3] Removing old firewall rules (if any)...
netsh advfirewall firewall delete rule name="HMS Port 8000" >nul 2>&1
netsh advfirewall firewall delete rule name="HMS Docker Port 8000" >nul 2>&1
echo    ✅ Old rules removed
echo.

echo [2/3] Adding new firewall rule for port 8000...
netsh advfirewall firewall add rule name="HMS Port 8000" dir=in action=allow protocol=TCP localport=8000
if %errorlevel% equ 0 (
    echo    ✅ Firewall rule added successfully!
) else (
    echo    ❌ Failed to add firewall rule
    pause
    exit /b 1
)
echo.

echo [3/3] Verifying firewall rule...
netsh advfirewall firewall show rule name="HMS Port 8000" | findstr /i "Enabled.*Yes" >nul 2>&1
if %errorlevel% equ 0 (
    echo    ✅ Firewall rule is active and enabled
) else (
    echo    ⚠️  Firewall rule exists but may not be enabled
    echo    Check Windows Firewall settings manually
)
echo.

echo ========================================
echo ✅ Firewall Configuration Complete!
echo ========================================
echo.
echo The firewall rule has been added. You can now:
echo 1. Start the server: START_WIFI_SERVER.bat
echo 2. Access from other devices using your IP address
echo.
echo To find your IP address, run: DIAGNOSE_WIFI_ACCESS.bat
echo.
pause




