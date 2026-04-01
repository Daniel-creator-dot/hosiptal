@echo off
setlocal enabledelayedexpansion
echo ========================================
echo Finding Your REAL WiFi IP Address
echo ========================================
echo.

echo Checking network adapters...
echo.

REM Get all adapters and their IPs
for /f "tokens=*" %%a in ('ipconfig /all ^| findstr /i /c:"adapter" /c:"IPv4"') do (
    echo %%a
)

echo.
echo ========================================
echo Your WiFi IP Addresses (for tablet):
echo ========================================
echo.

set IP_COUNT=0
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i /c:"IPv4"') do (
    set IP=%%a
    set IP=!IP: =!
    if "!IP!" neq "" (
        set /a IP_COUNT+=1
        set IP_!IP_COUNT!=!IP!
        
        REM Skip VMware/VirtualBox IPs
        echo !IP! | findstr /r "^192\.168\.233\." >nul 2>&1
        if !errorlevel! neq 0 (
            echo !IP! | findstr /r "^192\.168\.64\." >nul 2>&1
            if !errorlevel! neq 0 (
                echo !IP! | findstr /r "^172\.20\." >nul 2>&1
                if !errorlevel! neq 0 (
                    echo    http://!IP!:8000
                )
            )
        )
    )
)

echo.
echo ========================================
echo IMPORTANT:
echo ========================================
echo.
echo The IP address 192.168.233.1 is a VMware adapter (virtual).
echo You need to find your REAL WiFi adapter IP.
echo.
echo Look for an IP that starts with:
echo   - 192.168.0.x
echo   - 192.168.1.x  
echo   - 10.0.x.x
echo   - 10.95.x.x (this might be your WiFi)
echo.
echo Try these URLs on your tablet:
echo   http://10.95.170.143:8000
echo   http://192.168.64.1:8000
echo.
echo But FIRST, you MUST fix the firewall:
echo   1. Right-click: FIX_AND_TEST_NOW.bat
echo   2. Select "Run as administrator"
echo   3. Click "Yes"
echo.
pause




