@echo off
setlocal enabledelayedexpansion
echo ========================================
echo Testing Server Access
echo ========================================
echo.

echo [TEST 1] Checking if server is running...
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if %errorlevel% neq 0 (
    echo    ❌ Server is NOT running
    echo    Start server using: START_WIFI_SERVER.bat
    pause
    exit /b 1
)
echo    ✅ Server is running
echo.

echo [TEST 2] Checking server binding...
netstat -ano | findstr ":8000" | findstr "0.0.0.0" >nul 2>&1
if %errorlevel% equ 0 (
    echo    ✅ Server is bound to 0.0.0.0 (accessible from network)
) else (
    echo    ❌ Server is NOT bound to 0.0.0.0
    echo    ⚠️  Server is only accessible from localhost
    echo    ⚠️  Restart server using: START_WIFI_SERVER.bat
    pause
    exit /b 1
)
echo.

echo [TEST 3] Finding IP addresses...
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
    echo    ❌ No IP addresses found
    pause
    exit /b 1
)

echo    ✅ Found %IP_COUNT% IP address(es)
echo.

echo [TEST 4] Testing server from this computer...
echo.
for /l %%i in (1,1,%IP_COUNT%) do (
    call set CURRENT_IP=%%IP_%%i%%
    echo    Testing http://!CURRENT_IP!:8000...
    powershell -Command "$result = try { $response = Invoke-WebRequest -Uri 'http://!CURRENT_IP!:8000' -TimeoutSec 2 -UseBasicParsing; if ($response.StatusCode -eq 200) { '✅ SUCCESS - Server responds!' } else { '⚠️  Server responded with status: ' + $response.StatusCode } } catch { '❌ FAILED - ' + $_.Exception.Message }; Write-Host $result" 2>nul
    echo.
)

echo [TEST 5] Checking Windows Firewall...
netsh advfirewall firewall show rule name="HMS Port 8000" >nul 2>&1
if %errorlevel% equ 0 (
    echo    ✅ Firewall rule exists
    netsh advfirewall firewall show rule name="HMS Port 8000" | findstr /i "Enabled.*Yes" >nul 2>&1
    if %errorlevel% equ 0 (
        echo    ✅ Firewall rule is ENABLED
    ) else (
        echo    ⚠️  Firewall rule may be DISABLED
        echo    Run FIX_AND_TEST_NOW.bat as Administrator
    )
) else (
    echo    ❌ Firewall rule NOT FOUND
    echo    ⚠️  Port 8000 may be blocked by firewall
    echo    Run FIX_AND_TEST_NOW.bat as Administrator
)
echo.

echo ========================================
echo Test Complete
echo ========================================
echo.
echo If tests show SUCCESS but tablet still can't connect:
echo 1. Make sure tablet is on SAME WiFi network
echo 2. Check router AP Isolation settings
echo 3. Try temporarily disabling Windows Firewall
echo 4. Check antivirus software
echo.
pause




