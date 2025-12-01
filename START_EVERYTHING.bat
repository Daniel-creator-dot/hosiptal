@echo off
echo ========================================
echo STARTING HMS SERVER
echo ========================================
echo.

echo Step 1: Checking Docker Desktop...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ❌ Docker Desktop is NOT running!
    echo.
    echo Please:
    echo 1. Open Docker Desktop from Start Menu
    echo 2. Wait for it to fully start (whale icon in system tray)
    echo 3. Run this script again
    echo.
    pause
    exit /b 1
)

echo ✅ Docker Desktop is running
echo.

echo Step 2: Starting Docker services...
docker-compose up -d
if %errorlevel% neq 0 (
    echo ❌ Failed to start services
    pause
    exit /b 1
)
echo ✅ Services started
echo.

echo Step 3: Waiting for services to be ready...
timeout /t 15 /nobreak >nul
echo.

echo Step 4: Configuring Windows Firewall...
netsh advfirewall firewall delete rule name="HMS Docker Port 8000" >nul 2>&1
netsh advfirewall firewall add rule name="HMS Docker Port 8000" dir=in action=allow protocol=TCP localport=8000 >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Firewall configured
) else (
    echo ⚠️  Firewall rule needs Administrator
    echo    Please run allow_port_8000_firewall.bat as Administrator
)
echo.

echo Step 5: Checking status...
docker-compose ps
echo.

echo ========================================
echo ✅ HMS IS RUNNING!
echo ========================================
echo.
echo Access your application:
echo    Local:  http://localhost:8000
echo    Network: http://192.168.0.102:8000
echo.
echo If network access doesn't work:
echo    1. Run allow_port_8000_firewall.bat as Administrator
echo    2. Check: docker-compose logs web
echo.
pause














