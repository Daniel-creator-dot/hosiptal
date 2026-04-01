@echo off
setlocal enabledelayedexpansion
echo ========================================
echo WiFi Access Diagnostic Tool
echo ========================================
echo.

echo [1/6] Checking Python and Django...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo    ❌ Python not found!
    pause
    exit /b 1
)
echo    ✅ Python found

python -c "import django" >nul 2>&1
if %errorlevel% neq 0 (
    echo    ❌ Django not found!
    pause
    exit /b 1
)
echo    ✅ Django found
echo.

echo [2/6] Finding your network IP addresses...
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
    echo    ⚠️  No IP addresses found!
) else (
    echo    ✅ Found %IP_COUNT% IP address(es)
)
echo.

echo [3/6] Checking Windows Firewall...
echo.
netsh advfirewall firewall show rule name="HMS Port 8000" >nul 2>&1
if %errorlevel% equ 0 (
    echo    ✅ Firewall rule exists
    netsh advfirewall firewall show rule name="HMS Port 8000" | findstr /i "Enabled.*Yes" >nul 2>&1
    if %errorlevel% equ 0 (
        echo    ✅ Firewall rule is ENABLED
    ) else (
        echo    ⚠️  Firewall rule exists but may be DISABLED
    )
) else (
    echo    ❌ Firewall rule NOT FOUND
    echo    ⚠️  Port 8000 may be blocked!
)
echo.

echo [4/6] Checking if port 8000 is in use...
netstat -ano | findstr ":8000" >nul 2>&1
if %errorlevel% equ 0 (
    echo    ⚠️  Port 8000 is already in use:
    netstat -ano | findstr ":8000"
    echo.
    echo    You may need to stop the existing server first
) else (
    echo    ✅ Port 8000 is available
)
echo.

echo [5/6] Testing network connectivity...
echo    Testing if you can reach localhost...
ping -n 1 127.0.0.1 >nul 2>&1
if %errorlevel% equ 0 (
    echo    ✅ Localhost is reachable
) else (
    echo    ❌ Cannot reach localhost (unusual!)
)
echo.

echo [6/6] Checking administrator privileges...
net session >nul 2>&1
if %errorlevel% equ 0 (
    echo    ✅ Running as Administrator
    echo    ✅ Can configure firewall automatically
) else (
    echo    ⚠️  NOT running as Administrator
    echo    ⚠️  Cannot configure firewall automatically
    echo    ⚠️  You may need to run this script as Administrator
)
echo.

echo ========================================
echo Diagnostic Summary
echo ========================================
echo.

REM Check firewall
netsh advfirewall firewall show rule name="HMS Port 8000" >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ ISSUE FOUND: Firewall rule missing
    echo.
    echo FIX: Run this script as Administrator, or manually add firewall rule:
    echo    netsh advfirewall firewall add rule name="HMS Port 8000" dir=in action=allow protocol=TCP localport=8000
    echo.
) else (
    echo ✅ Firewall rule exists
)

REM Check if port is in use
netstat -ano | findstr ":8000" >nul 2>&1
if %errorlevel% equ 0 (
    echo ⚠️  Port 8000 is in use - make sure server is running with 0.0.0.0:8000
) else (
    echo ⚠️  Port 8000 is NOT in use - server is not running
    echo    Start the server first using START_WIFI_SERVER.bat
)

echo.
echo ========================================
echo Access URLs (use these on other devices):
echo ========================================
echo.
if %IP_COUNT% gtr 0 (
    for /l %%i in (1,1,%IP_COUNT%) do (
        call set CURRENT_IP=%%IP_%%i%%
        echo    http://!CURRENT_IP!:8000
    )
) else (
    echo    ⚠️  Could not detect IP addresses
    echo    Run 'ipconfig' to find your IP manually
)
echo.

echo ========================================
echo Next Steps:
echo ========================================
echo.
echo 1. If firewall rule is missing:
echo    - Right-click this file and "Run as administrator"
echo    - Or run: FIX_FIREWALL_NOW.bat (as admin)
echo.
echo 2. Start the server:
echo    - Run: START_WIFI_SERVER.bat
echo    - Make sure it shows "Starting development server at http://0.0.0.0:8000/"
echo.
echo 3. Test from this computer first:
echo    - Open browser and go to: http://localhost:8000
echo    - If this works, try: http://YOUR_IP:8000 (replace YOUR_IP)
echo.
echo 4. Test from other device:
echo    - Make sure device is on SAME WiFi network
echo    - Open browser and go to: http://YOUR_IP:8000
echo.
echo 5. If still not working:
echo    - Check router settings (disable AP Isolation)
echo    - Try temporarily disabling Windows Firewall to test
echo    - Check antivirus software
echo.
pause




