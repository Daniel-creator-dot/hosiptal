@echo off
setlocal enabledelayedexpansion
echo ========================================
echo Starting HMS Server - WiFi Access Mode
echo ========================================
echo.

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
echo ========================================
echo Finding Your WiFi IP Address
echo ========================================
echo.

REM Get WiFi IP addresses (exclude Docker/VirtualBox IPs)
set IP_COUNT=0
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i /c:"IPv4"') do (
    set IP=%%a
    set IP=!IP: =!
    if "!IP!" neq "" (
        set /a IP_COUNT+=1
        set IP_!IP_COUNT!=!IP!
    )
)

if %IP_COUNT% equ 0 (
    echo ⚠️  Could not detect IP address
    echo    Server will still start, but you may need to find your IP manually
    echo    Run: ipconfig
    echo.
) else (
    echo ✅ Found %IP_COUNT% network interface(s):
    for /l %%i in (1,1,%IP_COUNT%) do (
        call set CURRENT_IP=%%IP_%%i%%
        echo    http://!CURRENT_IP!:8000
    )
    echo.
)

echo ========================================
echo Configuring Windows Firewall
echo ========================================
echo.

REM Check if firewall rule exists
netsh advfirewall firewall show rule name="HMS Port 8000" >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️  Adding Windows Firewall rule for port 8000...
    echo    (This may require administrator privileges)
    netsh advfirewall firewall add rule name="HMS Port 8000" dir=in action=allow protocol=TCP localport=8000 >nul 2>&1
    if %errorlevel% equ 0 (
        echo ✅ Firewall rule added successfully!
    ) else (
        echo ⚠️  Could not add firewall rule automatically
        echo    You may need to allow port 8000 manually in Windows Firewall
        echo    Or run this script as Administrator
    )
) else (
    echo ✅ Firewall already configured
)
echo.

echo ========================================
echo Starting Django Development Server
echo ========================================
echo.
echo Server will be available at:
echo   - http://localhost:8000 (this computer)
echo   - http://127.0.0.1:8000 (this computer)
if %IP_COUNT% gtr 0 (
    echo   - From other devices on WiFi:
    for /l %%i in (1,1,%IP_COUNT%) do (
        call set CURRENT_IP=%%IP_%%i%%
        echo     http://!CURRENT_IP!:8000
    )
)
echo.
echo 📱 To access from phone/tablet:
echo    1. Make sure device is on the SAME WiFi network
echo    2. Open browser and go to one of the IP addresses above
echo    3. You should see the HMS login page
echo.
echo Press Ctrl+C to stop the server
echo.
echo ========================================
echo.

python manage.py runserver 0.0.0.0:8000

pause




