@echo off
echo ========================================
echo FIXING AND STARTING HMS
echo ========================================
echo.

echo [1/5] Checking Docker Desktop...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo    ERROR: Docker Desktop is not running!
    echo    Please start Docker Desktop manually, then run this script again.
    echo    Or wait 30 seconds for Docker Desktop to start...
    timeout /t 30 /nobreak
    docker info >nul 2>&1
    if %errorlevel% neq 0 (
        echo    ERROR: Docker Desktop still not running!
        echo    Please start Docker Desktop and try again.
        pause
        exit /b 1
    )
)
echo    OK: Docker Desktop is running
echo.

echo [2/5] Starting Docker services...
docker-compose up -d
if %errorlevel% neq 0 (
    echo    ERROR: Failed to start services
    pause
    exit /b 1
)
echo    OK: Services starting...
echo.

echo [3/5] Waiting for services to be ready...
timeout /t 10 /nobreak >nul
echo.

echo [4/5] Configuring Windows Firewall...
netsh advfirewall firewall delete rule name="HMS Docker Port 8000" >nul 2>&1
netsh advfirewall firewall add rule name="HMS Docker Port 8000" dir=in action=allow protocol=TCP localport=8000
if %errorlevel% equ 0 (
    echo    OK: Firewall rule added
) else (
    echo    WARNING: Could not add firewall rule (may need Administrator)
    echo    Please run allow_port_8000_firewall.bat as Administrator
)
echo.

echo [5/5] Checking service status...
docker-compose ps
echo.

echo ========================================
echo SETUP COMPLETE!
echo ========================================
echo.
echo Your HMS application should be accessible at:
echo    http://192.168.0.102:8000
echo    http://localhost:8000
echo.
echo If it's still not working:
echo    1. Check Docker Desktop is fully started
echo    2. Run allow_port_8000_firewall.bat as Administrator
echo    3. Check: docker-compose logs web
echo.
pause














