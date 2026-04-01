@echo off
setlocal enabledelayedexpansion
echo ========================================
echo WiFi Connection Test Tool
echo ========================================
echo.

echo [TEST 1] Checking if server is running...
netstat -ano | findstr ":8000" >nul 2>&1
if %errorlevel% neq 0 (
    echo    ❌ Server is NOT running on port 8000
    echo    Please start the server first using START_WIFI_SERVER.bat
    echo.
    pause
    exit /b 1
)

echo    ✅ Server is running on port 8000
echo    Checking which interface it's bound to...
netstat -ano | findstr ":8000"
echo.

echo [TEST 2] Finding your network IP addresses...
echo.
set IP_COUNT=0
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i /c:"IPv4"') do (
    set IP=%%a
    set IP=!IP: =!
    if "!IP!" neq "" (
        set /a IP_COUNT+=1
        set IP_!IP_COUNT!=!IP!
        echo    IP !IP_COUNT!: !IP!
    )
)
echo.

if %IP_COUNT% equ 0 (
    echo    ❌ No IP addresses found!
    pause
    exit /b 1
)

echo [TEST 3] Testing server accessibility from this computer...
echo.
echo    Testing localhost...
curl -s -o nul -w "HTTP Status: %%{http_code}\n" http://localhost:8000 2>nul
if %errorlevel% equ 0 (
    echo    ✅ Server responds on localhost
) else (
    echo    ⚠️  Could not test localhost (curl may not be installed)
    echo    Try opening http://localhost:8000 in your browser
)
echo.

echo    Testing with IP addresses...
for /l %%i in (1,1,%IP_COUNT%) do (
    call set CURRENT_IP=%%IP_%%i%%
    echo    Testing http://!CURRENT_IP!:8000...
    curl -s -o nul -w "HTTP Status: %%{http_code}\n" http://!CURRENT_IP!:8000 2>nul
    if !errorlevel! neq 0 (
        echo    ⚠️  Could not test (curl may not be installed)
    )
)
echo.

echo [TEST 4] Checking Windows Firewall...
echo.
netsh advfirewall firewall show rule name="HMS Port 8000" >nul 2>&1
if %errorlevel% equ 0 (
    echo    ✅ Firewall rule exists
    netsh advfirewall firewall show rule name="HMS Port 8000" | findstr /i "Enabled.*Yes" >nul 2>&1
    if %errorlevel% equ 0 (
        echo    ✅ Firewall rule is ENABLED
    ) else (
        echo    ❌ Firewall rule is DISABLED - this may block connections!
        echo    FIX: Enable the rule in Windows Firewall settings
    )
) else (
    echo    ❌ Firewall rule NOT FOUND - port 8000 may be blocked!
    echo    FIX: Run FIX_FIREWALL_NOW.bat as Administrator
)
echo.

echo [TEST 5] Checking if server is bound to 0.0.0.0...
echo.
netstat -ano | findstr ":8000" | findstr "0.0.0.0" >nul 2>&1
if %errorlevel% equ 0 (
    echo    ✅ Server is bound to 0.0.0.0 (all interfaces) - GOOD!
) else (
    echo    ⚠️  Server may not be bound to all interfaces
    echo    Make sure you started with: python manage.py runserver 0.0.0.0:8000
)
echo.

echo ========================================
echo Connection Test Summary
echo ========================================
echo.
echo Your server should be accessible at:
for /l %%i in (1,1,%IP_COUNT%) do (
    call set CURRENT_IP=%%IP_%%i%%
    echo    http://!CURRENT_IP!:8000
)
echo.

echo To test from another device:
echo 1. Make sure device is on the SAME WiFi network
echo 2. Open browser and go to one of the IP addresses above
echo 3. If it doesn't work, check:
echo    - Windows Firewall (run FIX_FIREWALL_NOW.bat as admin)
echo    - Router AP Isolation settings (disable if enabled)
echo    - Antivirus software (may be blocking connections)
echo    - Try temporarily disabling Windows Firewall to test
echo.

pause




