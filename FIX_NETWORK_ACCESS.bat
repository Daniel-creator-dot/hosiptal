@echo off
echo.
echo ========================================
echo   Fix Network Access for Other Devices
echo ========================================
echo.

REM Get current IP address
echo [1/4] Detecting current IP address...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    set IP_LINE=%%a
    set IP_LINE=!IP_LINE: =!
    for /f "tokens=1" %%b in ("!IP_LINE!") do (
        set CURRENT_IP=%%b
        echo    Found IP: !CURRENT_IP!
        goto :found_ip
    )
)

:found_ip
if "%CURRENT_IP%"=="" (
    echo    ⚠️  Could not detect IP automatically
    set /p CURRENT_IP="Enter your computer's IP address: "
)

echo.
echo [2/4] Checking Docker Desktop...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Docker Desktop is not running!
    pause
    exit /b 1
)
echo    ✅ Docker Desktop is running
echo.

REM Get Docker gateway IP (usually 172.x.x.1)
echo [3/4] Detecting Docker gateway IP...
for /f "tokens=2" %%a in ('docker network inspect bridge ^| findstr "Gateway"') do (
    set DOCKER_IP=%%a
    set DOCKER_IP=!DOCKER_IP:"=!
    set DOCKER_IP=!DOCKER_IP:,=!
    echo    Found Docker IP: !DOCKER_IP!
    goto :found_docker_ip
)

:found_docker_ip
if "%DOCKER_IP%"=="" (
    set DOCKER_IP=172.19.144.1
    echo    Using default Docker IP: %DOCKER_IP%
)

echo.
echo [4/4] Updating docker-compose.yml with IPs...
echo    Current IP: %CURRENT_IP%
echo    Docker IP: %DOCKER_IP%
echo.

REM Update docker-compose.yml
powershell -Command "(Get-Content docker-compose.yml) -replace 'ALLOWED_HOSTS=.*', 'ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,%CURRENT_IP%,%DOCKER_IP%' | Set-Content docker-compose.yml"
powershell -Command "(Get-Content docker-compose.yml) -replace 'CSRF_TRUSTED_ORIGINS=.*', 'CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,http://0.0.0.0:8000,http://%CURRENT_IP%:8000,http://%DOCKER_IP%:8000' | Set-Content docker-compose.yml"

echo    ✅ Configuration updated
echo.

REM Restart web service
echo [5/5] Restarting web service...
docker-compose restart web
echo.

echo ========================================
echo   ✅ NETWORK ACCESS FIXED!
echo ========================================
echo.
echo Access URLs:
echo   Local:    http://localhost:8000
echo   Network:  http://%CURRENT_IP%:8000
echo.
echo If other devices still can't access:
echo   1. Check Windows Firewall (allow port 8000)
echo   2. Ensure devices are on same network
echo   3. Try: http://%CURRENT_IP%:8000 from another device
echo.
pause
