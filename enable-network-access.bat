@echo off
REM ========================================
REM 🌐 ENABLE NETWORK ACCESS FOR HMS
REM ========================================
echo.
echo ========================================
echo   🌐 ENABLE NETWORK ACCESS
echo ========================================
echo.

REM Get local IP address
echo [1/3] Getting your local IP address...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    set LOCAL_IP=%%a
    goto :found
)
:found
set LOCAL_IP=%LOCAL_IP: =%
echo    Your IP Address: %LOCAL_IP%
echo.

REM Check if Docker is running
echo [2/3] Checking Docker...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo    ❌ Docker Desktop is not running!
    echo    Please start Docker Desktop and try again.
    pause
    exit /b 1
)
echo    ✅ Docker is running
echo.

REM Check if web container is running
echo [3/3] Checking web container...
docker ps --format "{{.Names}}" | findstr /i "web" >nul 2>&1
if %errorlevel% neq 0 (
    echo    ⚠️  Web container is not running!
    echo    Starting containers...
    docker-compose up -d
    timeout /t 10 /nobreak >nul
    echo    ✅ Containers started
) else (
    echo    ✅ Web container is running
)
echo.

REM Check Windows Firewall
echo [4/4] Checking Windows Firewall...
netsh advfirewall firewall show rule name="HMS Docker Port 8000" >nul 2>&1
if %errorlevel% neq 0 (
    echo    ⚠️  Adding firewall rule for port 8000...
    echo    ⚠️  NOTE: This requires administrator privileges!
    echo    ⚠️  If this fails, run this script as Administrator
    echo.
    netsh advfirewall firewall add rule name="HMS Docker Port 8000" dir=in action=allow protocol=TCP localport=8000 2>nul
    if %errorlevel% equ 0 (
        echo    ✅ Firewall rule added
    ) else (
        echo    ⚠️  Could not add firewall rule (needs admin)
        echo    ⚠️  You may need to manually allow port 8000 in Windows Firewall
        echo    ⚠️  Or run this script as Administrator
    )
) else (
    echo    ✅ Firewall configured
)
echo.

echo ========================================
echo   ✅ NETWORK ACCESS ENABLED!
echo ========================================
echo.
echo 🌐 Access URLs:
echo.
echo    From this computer:
echo    http://localhost:8000
echo    http://127.0.0.1:8000
echo.
echo    From other devices on WiFi:
echo    http://%LOCAL_IP%:8000
echo.
echo 📱 To access from phone/tablet:
echo    1. Make sure your device is on the same WiFi network
echo    2. Open browser and go to: http://%LOCAL_IP%:8000
echo    3. You should see the HMS login page
echo.
echo ⚠️  If you can't access:
echo    - Make sure Windows Firewall allows port 8000
echo    - Make sure devices are on the same WiFi network
echo    - Try disabling Windows Firewall temporarily to test
echo.
pause

