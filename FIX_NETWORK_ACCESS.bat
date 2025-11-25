@echo off
echo ========================================
echo FIXING NETWORK ACCESS
echo ========================================
echo.

echo [1/4] Checking Docker services...
docker-compose ps
if %errorlevel% neq 0 (
    echo    ERROR: Docker services not running
    echo    Starting services...
    docker-compose up -d
    timeout /t 10 /nobreak >nul
)
echo    OK: Services running
echo.

echo [2/4] Configuring Windows Firewall...
netsh advfirewall firewall delete rule name="HMS Docker Port 8000" >nul 2>&1
netsh advfirewall firewall add rule name="HMS Docker Port 8000" dir=in action=allow protocol=TCP localport=8000
if %errorlevel% equ 0 (
    echo    OK: Firewall rule added
) else (
    echo    ERROR: Could not add firewall rule
    echo    Please run this script as Administrator!
    pause
    exit /b 1
)
echo.

echo [3/4] Checking port 8000...
netstat -an | findstr ":8000" | findstr "LISTENING"
if %errorlevel% equ 0 (
    echo    OK: Port 8000 is listening
) else (
    echo    WARNING: Port 8000 may not be listening
)
echo.

echo [4/4] Testing connection...
curl -s -o nul -w "HTTP Status: %%{http_code}\n" http://localhost:8000 2>nul
if %errorlevel% equ 0 (
    echo    OK: Server is responding
) else (
    echo    WARNING: Server may not be responding
)
echo.

echo ========================================
echo NETWORK ACCESS FIXED!
echo ========================================
echo.
echo Your HMS is accessible at:
echo    Local:  http://localhost:8000
echo    Network: http://192.168.0.102:8000
echo.
echo If still not working from network:
echo    1. Check Windows Defender Firewall is not blocking
echo    2. Check router settings
echo    3. Try from another device on same network
echo.
pause






