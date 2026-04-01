@echo off
setlocal enabledelayedexpansion
echo ========================================
echo COMPLETE FIX AND TEST FOR WIFI ACCESS
echo ========================================
echo.

REM Check admin first
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ NOT running as Administrator!
    echo.
    echo This script MUST be run as Administrator to fix firewall.
    echo.
    echo TO FIX:
    echo 1. Close this window
    echo 2. Right-click this file
    echo 3. Select "Run as administrator"
    echo 4. Click "Yes"
    echo.
    pause
    exit /b 1
)

echo ✅ Running as Administrator
echo.

echo [STEP 1/6] Removing old firewall rules...
netsh advfirewall firewall delete rule name="HMS Port 8000" >nul 2>&1
netsh advfirewall firewall delete rule name="HMS Docker Port 8000" >nul 2>&1
echo    ✅ Old rules removed
echo.

echo [STEP 2/6] Adding Windows Firewall rule for port 8000...
netsh advfirewall firewall add rule name="HMS Port 8000" dir=in action=allow protocol=TCP localport=8000
if %errorlevel% equ 0 (
    echo    ✅ Firewall rule added successfully!
) else (
    echo    ❌ Failed to add firewall rule
    pause
    exit /b 1
)
echo.

echo [STEP 3/6] Verifying firewall rule...
netsh advfirewall firewall show rule name="HMS Port 8000" | findstr /i "Enabled.*Yes" >nul 2>&1
if %errorlevel% equ 0 (
    echo    ✅ Firewall rule is active
) else (
    echo    ⚠️  Firewall rule exists but may need manual enable
)
echo.

echo [STEP 4/6] Finding your IP addresses...
echo.
set IP_COUNT=0
set PRIMARY_IP=
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i /c:"IPv4"') do (
    set IP=%%a
    set IP=!IP: =!
    if "!IP!" neq "" (
        set /a IP_COUNT+=1
        set IP_!IP_COUNT!=!IP!
        
        REM Prefer 192.168.x.x as primary
        echo !IP! | findstr /r "^192\.168\." >nul 2>&1
        if !errorlevel! equ 0 (
            if "!PRIMARY_IP!"=="" set PRIMARY_IP=!IP!
        )
    )
)

if "!PRIMARY_IP!"=="" (
    if %IP_COUNT% gtr 0 (
        call set PRIMARY_IP=%%IP_1%%
    )
)

if %IP_COUNT% gtr 0 (
    echo    ✅ Found %IP_COUNT% IP address(es):
    for /l %%i in (1,1,%IP_COUNT%) do (
        call set CURRENT_IP=%%IP_%%i%%
        echo       !CURRENT_IP!
    )
    echo.
    echo    PRIMARY IP: !PRIMARY_IP!
) else (
    echo    ❌ No IP addresses found!
)
echo.

echo [STEP 5/6] Checking if server is running...
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo    ✅ Server is running on port 8000
    echo.
    echo    Server status:
    netstat -ano | findstr ":8000" | findstr "LISTENING"
    echo.
    
    REM Check if bound to 0.0.0.0
    netstat -ano | findstr ":8000" | findstr "0.0.0.0" >nul 2>&1
    if %errorlevel% equ 0 (
        echo    ✅ Server is bound to 0.0.0.0 (accessible from network)
    ) else (
        echo    ❌ Server is NOT bound to 0.0.0.0
        echo    ⚠️  Server may only be accessible from localhost
        echo    ⚠️  You need to restart server with: START_WIFI_SERVER.bat
    )
) else (
    echo    ❌ Server is NOT running!
    echo    ⚠️  You need to start the server first
    echo    ⚠️  Run: START_WIFI_SERVER.bat
)
echo.

echo [STEP 6/6] Testing local connectivity...
if "!PRIMARY_IP!" neq "" (
    echo    Testing http://!PRIMARY_IP!:8000 from this computer...
    powershell -Command "$response = try { Invoke-WebRequest -Uri 'http://!PRIMARY_IP!:8000' -TimeoutSec 3 -UseBasicParsing; 'SUCCESS' } catch { 'FAILED' }; Write-Host $response" 2>nul
    if !errorlevel! equ 0 (
        echo    ✅ Server responds on network IP
    ) else (
        echo    ⚠️  Could not test (server may still be starting)
    )
) else (
    echo    ⚠️  Cannot test - no IP address found
)
echo.

echo ========================================
echo ✅ FIX COMPLETE!
echo ========================================
echo.
echo YOUR TABLET CONNECTION URL:
echo.
if "!PRIMARY_IP!" neq "" (
    echo    http://!PRIMARY_IP!:8000
    echo.
    echo Copy this URL and use it on your tablet!
) else (
    echo    ⚠️  Could not determine IP address
    echo    Run 'ipconfig' to find it manually
)
echo.

echo ========================================
echo NEXT STEPS:
echo ========================================
echo.
echo 1. Make sure server is running:
echo    - If not running, start it: START_WIFI_SERVER.bat
echo    - Look for: "Starting development server at http://0.0.0.0:8000/"
echo.
echo 2. On your tablet:
echo    - Make sure tablet is on SAME WiFi network
echo    - Open browser
echo    - Go to: http://!PRIMARY_IP!:8000
echo.
echo 3. If still not working:
echo    - Try other IP addresses (run GET_IP_AND_CONNECT.bat)
echo    - Check router AP Isolation settings
echo    - Try temporarily disabling Windows Firewall to test
echo    - Check antivirus software
echo.

pause




