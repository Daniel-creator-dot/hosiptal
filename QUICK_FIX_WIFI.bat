@echo off
echo ========================================
echo Quick Fix for WiFi Access Issues
echo ========================================
echo.
echo This script will:
echo 1. Fix Windows Firewall (requires admin)
echo 2. Show your IP address
echo 3. Test if server is running
echo 4. Provide next steps
echo.

REM Check admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️  NOT running as Administrator
    echo.
    echo To fix firewall automatically, you need to run as admin:
    echo 1. Right-click this file
    echo 2. Select "Run as administrator"
    echo 3. Click "Yes"
    echo.
    echo Continuing without admin privileges...
    echo.
) else (
    echo ✅ Running as Administrator
    echo.
    echo [1/4] Fixing Windows Firewall...
    netsh advfirewall firewall delete rule name="HMS Port 8000" >nul 2>&1
    netsh advfirewall firewall add rule name="HMS Port 8000" dir=in action=allow protocol=TCP localport=8000
    if %errorlevel% equ 0 (
        echo    ✅ Firewall rule added successfully!
    ) else (
        echo    ❌ Failed to add firewall rule
    )
    echo.
)

echo [2/4] Finding your IP address...
echo.
setlocal enabledelayedexpansion
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

echo [3/4] Checking if server is running...
netstat -ano | findstr ":8000" >nul 2>&1
if %errorlevel% equ 0 (
    echo    ✅ Server is running on port 8000
    echo.
    echo    Server status:
    netstat -ano | findstr ":8000"
    echo.
    
    REM Check if bound to 0.0.0.0
    netstat -ano | findstr ":8000" | findstr "0.0.0.0" >nul 2>&1
    if %errorlevel% equ 0 (
        echo    ✅ Server is bound to 0.0.0.0 (accessible from network)
    ) else (
        echo    ❌ Server is NOT bound to 0.0.0.0
        echo    ⚠️  Server may only be accessible from localhost
        echo    ⚠️  Restart server using: START_WIFI_SERVER.bat
    )
) else (
    echo    ❌ Server is NOT running
    echo    ⚠️  Start the server using: START_WIFI_SERVER.bat
)
echo.

echo [4/4] Summary and Next Steps
echo ========================================
echo.

if %IP_COUNT% gtr 0 (
    echo ✅ Your IP address(es):
    for /l %%i in (1,1,%IP_COUNT%) do (
        call set CURRENT_IP=%%IP_%%i%%
        echo    http://!CURRENT_IP!:8000
    )
    echo.
) else (
    echo ⚠️  Could not detect IP address
    echo    Run 'ipconfig' to find it manually
    echo.
)

echo 📱 To access from other devices:
echo    1. Make sure device is on SAME WiFi network
echo    2. Open browser and go to: http://YOUR_IP:8000
echo    3. Replace YOUR_IP with one of the addresses above
echo.

echo 🔧 If still not working:
echo    1. Run: DIAGNOSE_WIFI_ACCESS.bat (for detailed diagnostics)
echo    2. Run: TEST_WIFI_CONNECTION.bat (to test connectivity)
echo    3. Check: TROUBLESHOOT_WIFI.md (for detailed guide)
echo    4. Make sure router AP Isolation is disabled
echo    5. Try temporarily disabling Windows Firewall to test
echo.

pause




