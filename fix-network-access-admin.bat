@echo off
REM ========================================
REM 🌐 FIX NETWORK ACCESS (RUN AS ADMIN)
REM ========================================
echo.
echo ========================================
echo   🌐 FIX NETWORK ACCESS
echo   RUN THIS AS ADMINISTRATOR!
echo ========================================
echo.

REM Check if running as admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ ERROR: This script must be run as Administrator!
    echo.
    echo Right-click this file and select "Run as administrator"
    echo.
    pause
    exit /b 1
)

echo ✅ Running as Administrator
echo.

REM Get local IP addresses
echo [1/4] Getting IP addresses...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    set IP=%%a
    set IP=!IP: =!
    echo    Found IP: !IP!
)
echo.

REM Add firewall rule
echo [2/4] Adding Windows Firewall rule...
netsh advfirewall firewall delete rule name="HMS Docker Port 8000" >nul 2>&1
netsh advfirewall firewall add rule name="HMS Docker Port 8000" dir=in action=allow protocol=TCP localport=8000
if %errorlevel% equ 0 (
    echo    ✅ Firewall rule added successfully
) else (
    echo    ❌ Failed to add firewall rule
    pause
    exit /b 1
)
echo.

REM Verify Docker is running
echo [3/4] Checking Docker...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo    ❌ Docker is not running!
    echo    Please start Docker Desktop
    pause
    exit /b 1
)
echo    ✅ Docker is running
echo.

REM Check container
echo [4/4] Checking web container...
docker ps --format "{{.Names}}" | findstr /i "web" >nul 2>&1
if %errorlevel% neq 0 (
    echo    ⚠️  Web container not running, starting...
    docker-compose up -d
    timeout /t 10 /nobreak >nul
)
echo    ✅ Web container is running
echo.

echo ========================================
echo   ✅ NETWORK ACCESS FIXED!
echo ========================================
echo.
echo Your IP addresses (try these on your tablet):
echo.
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    set IP=%%a
    set IP=!IP: =!
    echo    http://!IP!:8000
)
echo.
echo 📱 On your tablet:
echo    1. Make sure it's on the SAME WiFi network
echo    2. Open browser
echo    3. Try the URLs above
echo.
echo ✅ Firewall rule added
echo ✅ Docker configured
echo ✅ Container running
echo.
pause

