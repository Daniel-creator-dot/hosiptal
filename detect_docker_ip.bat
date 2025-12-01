@echo off
setlocal enabledelayedexpansion
echo.
echo ========================================
echo   Docker IP Detection Tool
echo ========================================
echo.

REM Check if Docker is running
echo [1/3] Checking Docker Desktop...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Docker Desktop is not running!
    echo    Please start Docker Desktop and try again.
    echo.
    pause
    exit /b 1
)
echo    ✅ Docker Desktop is running
echo.

REM Detect local network IP
echo [2/3] Detecting local network IP...
set LOCAL_IP=
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    set IP_LINE=%%a
    set IP_LINE=!IP_LINE: =!
    for /f "tokens=1" %%b in ("!IP_LINE!") do (
        set TEST_IP=%%b
        echo !TEST_IP! | findstr /r "^192\.168\." >nul
        if !errorlevel! equ 0 (
            set LOCAL_IP=!TEST_IP!
            goto :found_ip
        )
        echo !TEST_IP! | findstr /r "^10\." >nul
        if !errorlevel! equ 0 (
            set LOCAL_IP=!TEST_IP!
            goto :found_ip
        )
        echo !TEST_IP! | findstr /r "^172\.1[6-9]\." >nul
        if !errorlevel! equ 0 (
            set LOCAL_IP=!TEST_IP!
            goto :found_ip
        )
        echo !TEST_IP! | findstr /r "^172\.2[0-9]\." >nul
        if !errorlevel! equ 0 (
            set LOCAL_IP=!TEST_IP!
            goto :found_ip
        )
        echo !TEST_IP! | findstr /r "^172\.3[0-1]\." >nul
        if !errorlevel! equ 0 (
            set LOCAL_IP=!TEST_IP!
            goto :found_ip
        )
    )
)
:found_ip

echo.
echo ========================================
echo   Detection Results
echo ========================================
echo.
echo Docker Desktop Host IP:
echo    Use: host.docker.internal
echo    (This is the special DNS name Docker provides)
echo.
if "%LOCAL_IP%"=="" (
    echo Local Network IP:
    echo    ⚠️  NOT DETECTED
    echo.
    echo    Possible reasons:
    echo    - Not connected to a network
    echo    - Network uses different IP range
    echo    - VPN or special network configuration
    echo.
    echo    You can manually find your IP:
    echo    1. Run: ipconfig
    echo    2. Look for "IPv4 Address" under your network adapter
    echo    3. Update docker-compose.yml manually
) else (
    echo Local Network IP:
    echo    ✅ Detected: %LOCAL_IP%
    echo.
    echo    This IP should be added to:
    echo    - ALLOWED_HOSTS in docker-compose.yml
    echo    - CSRF_TRUSTED_ORIGINS in docker-compose.yml
    echo.
    echo    Access URL: http://%LOCAL_IP%:8000
)
echo.
echo ========================================
echo   Configuration Help
echo ========================================
echo.
echo For DATABASE_URL (in .env file):
echo    Use: host.docker.internal
echo    Example: DATABASE_URL=postgresql://user:pass@host.docker.internal:5432/db
echo.
echo For docker-compose.yml:
echo    Add your IP to ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS
echo    Or run: configure_network_access.ps1
echo.
pause





