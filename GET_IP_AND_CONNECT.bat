@echo off
setlocal enabledelayedexpansion
echo ========================================
echo YOUR IP ADDRESS FOR TABLET CONNECTION
echo ========================================
echo.
echo Finding your WiFi IP address...
echo.

set PRIMARY_IP=
set IP_COUNT=0

REM Get all IP addresses
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i /c:"IPv4"') do (
    set IP=%%a
    set IP=!IP: =!
    if "!IP!" neq "" (
        set /a IP_COUNT+=1
        set IP_!IP_COUNT!=!IP!
        
        REM Prefer 192.168.x.x or 10.x.x.x as primary
        echo !IP! | findstr /r "^192\.168\." >nul 2>&1
        if !errorlevel! equ 0 (
            if "!PRIMARY_IP!"=="" set PRIMARY_IP=!IP!
        )
        echo !IP! | findstr /r "^10\." >nul 2>&1
        if !errorlevel! equ 0 (
            if "!PRIMARY_IP!"=="" set PRIMARY_IP=!IP!
        )
    )
)

REM If no preferred IP found, use first one
if "!PRIMARY_IP!"=="" (
    if %IP_COUNT% gtr 0 (
        call set PRIMARY_IP=%%IP_1%%
    )
)

echo ========================================
echo CONNECT YOUR TABLET USING THIS URL:
echo ========================================
echo.
if "!PRIMARY_IP!" neq "" (
    echo    http://!PRIMARY_IP!:8000
    echo.
    echo Copy this URL and use it on your tablet!
) else (
    echo    ⚠️  Could not detect IP address
    echo    Run 'ipconfig' to find it manually
)
echo.

echo ========================================
echo ALL YOUR IP ADDRESSES (try these if first doesn't work):
echo ========================================
echo.
if %IP_COUNT% gtr 0 (
    for /l %%i in (1,1,%IP_COUNT%) do (
        call set CURRENT_IP=%%IP_%%i%%
        echo    http://!CURRENT_IP!:8000
    )
) else (
    echo    No IP addresses found
)
echo.

echo ========================================
echo IMPORTANT STEPS:
echo ========================================
echo.
echo 1. Make sure server is running:
echo    - Run: START_WIFI_SERVER.bat
echo    - Or: START_LOCAL_SERVER.bat
echo.
echo 2. On your tablet:
echo    - Make sure tablet is on SAME WiFi network
echo    - Open browser
echo    - Go to: http://!PRIMARY_IP!:8000
echo    - You should see the HMS login page
echo.
echo 3. If it doesn't work:
echo    - Try the other IP addresses above
echo    - Make sure Windows Firewall allows port 8000
echo    - Check router settings (disable AP Isolation)
echo.

pause




