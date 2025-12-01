@echo off
REM ========================================
REM 🔍 TEST NETWORK ACCESS
REM ========================================
echo.
echo ========================================
echo   🔍 TESTING NETWORK ACCESS
echo ========================================
echo.

echo [1/5] Checking Docker container...
docker ps --format "{{.Names}}\t{{.Ports}}" | findstr web
if %errorlevel% neq 0 (
    echo    ❌ Web container not running!
    echo    Starting containers...
    docker-compose up -d
    timeout /t 10 /nobreak >nul
)
echo    ✅ Container check complete
echo.

echo [2/5] Checking port binding...
netstat -an | findstr "0.0.0.0:8000" | findstr LISTENING
if %errorlevel% equ 0 (
    echo    ✅ Port 8000 is listening on all interfaces
) else (
    echo    ❌ Port 8000 not listening on 0.0.0.0
)
echo.

echo [3/5] Checking firewall rule...
netsh advfirewall firewall show rule name="HMS Docker Port 8000" >nul 2>&1
if %errorlevel% equ 0 (
    echo    ✅ Firewall rule exists
) else (
    echo    ❌ Firewall rule NOT found!
    echo    ⚠️  Run fix-network-access-admin.bat as Administrator
)
echo.

echo [4/5] Testing local access...
curl -s http://localhost:8000/health/ >nul 2>&1
if %errorlevel% equ 0 (
    echo    ✅ Local access works
) else (
    echo    ❌ Local access failed
)
echo.

echo [5/5] Your IP addresses:
echo.
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    set IP=%%a
    set IP=!IP: =!
    echo    IP: !IP!
    echo    URL: http://!IP!:8000
    echo.
)
echo.

echo ========================================
echo   📋 SUMMARY
echo ========================================
echo.
echo If firewall rule is missing:
echo    → Run fix-network-access-admin.bat as Administrator
echo.
echo If port is not listening:
echo    → Restart: docker-compose restart web
echo.
echo To test from tablet:
echo    → Make sure same WiFi network
echo    → Try the URLs shown above
echo.
pause

