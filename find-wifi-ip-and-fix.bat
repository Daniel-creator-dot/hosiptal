@echo off
REM ========================================
REM 🌐 FIND WiFi IP AND FIX ACCESS
REM ========================================
echo.
echo ========================================
echo   🌐 FIND WiFi IP AND FIX ACCESS
echo ========================================
echo.

echo [1/4] Finding WiFi IP address...
echo.
echo Your WiFi IP addresses (try these on your tablet):
echo.

REM Get WiFi IPs (exclude VMware, Hyper-V, etc.)
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i /c:"IPv4"') do (
    set IP=%%a
    set IP=!IP: =!
    echo    http://!IP!:8000
)

echo.
echo [2/4] Checking if running as Administrator...
net session >nul 2>&1
if %errorlevel% equ 0 (
    echo    ✅ Running as Administrator
    echo.
    echo [3/4] Adding Windows Firewall rule...
    netsh advfirewall firewall delete rule name="HMS Docker Port 8000" >nul 2>&1
    netsh advfirewall firewall add rule name="HMS Docker Port 8000" dir=in action=allow protocol=TCP localport=8000
    if %errorlevel% equ 0 (
        echo    ✅ Firewall rule added successfully!
    ) else (
        echo    ❌ Failed to add firewall rule
    )
) else (
    echo    ⚠️  NOT running as Administrator
    echo    ⚠️  Firewall rule cannot be added automatically
    echo.
    echo    TO FIX: Right-click this file and "Run as administrator"
    echo    OR run: fix-network-access-admin.bat (as admin)
)

echo.
echo [4/4] Checking Docker...
docker ps --format "{{.Names}}\t{{.Ports}}" | findstr web
if %errorlevel% neq 0 (
    echo    ⚠️  Web container not running
    echo    Starting containers...
    docker-compose up -d
    timeout /t 10 /nobreak >nul
)
echo.

echo ========================================
echo   📱 ACCESS FROM YOUR TABLET
echo ========================================
echo.
echo 1. Make sure tablet is on the SAME WiFi network
echo 2. Open browser on tablet
echo 3. Try these URLs (one should work):
echo.
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i /c:"IPv4"') do (
    set IP=%%a
    set IP=!IP: =!
    echo    http://!IP!:8000
)
echo.
echo ⚠️  If none work:
echo    - Check firewall (run fix-network-access-admin.bat as admin)
echo    - Make sure same WiFi network
echo    - Check router doesn't have AP isolation
echo.
pause

