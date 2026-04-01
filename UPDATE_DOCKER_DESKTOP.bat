@echo off
echo.
echo ========================================
echo   Docker Desktop Update
echo ========================================
echo.

REM Check current Docker version
echo [1/4] Checking current Docker version...
docker --version 2>nul
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Docker is not installed or not running!
    echo    Please install Docker Desktop first.
    echo    Download from: https://www.docker.com/products/docker-desktop/
    echo.
    pause
    exit /b 1
)

docker-compose --version 2>nul
echo    ✅ Docker is installed
echo.

REM Check if Docker Desktop is running
echo [2/4] Checking if Docker Desktop is running...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo    ⚠️  WARNING: Docker Desktop is not running!
    echo    Starting Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo    Please wait 30 seconds for Docker Desktop to start...
    timeout /t 30 /nobreak >nul
    
    REM Check again
    docker info >nul 2>&1
    if %errorlevel% neq 0 (
        echo    ❌ ERROR: Docker Desktop failed to start!
        echo    Please start Docker Desktop manually and try again.
        echo.
        pause
        exit /b 1
    )
)
echo    ✅ Docker Desktop is running
echo.

REM Stop containers before update (recommended)
echo [3/4] Checking running containers...
docker ps --format "{{.Names}}" >nul 2>&1
if %errorlevel% equ 0 (
    echo    Do you want to stop all containers before updating? (Y/N)
    set /p stop_containers="   Enter choice: "
    if /i "%stop_containers%"=="Y" (
        echo    Stopping containers...
        docker-compose down
        echo    ✅ Containers stopped
    ) else (
        echo    ⚠️  Containers will continue running during update
    )
)
echo.

REM Update instructions
echo [4/4] Docker Desktop Update Instructions
echo ========================================
echo.
echo METHOD 1: Using Docker Desktop (Easiest - Recommended)
echo.
echo    1. Open Docker Desktop
echo    2. Click the Settings icon (gear) in the top-right
echo    3. Go to "Software Updates" section
echo    4. Click "Check for Updates"
echo    5. If update is available, click "Download and Install"
echo    6. Wait for installation to complete
echo    7. Docker Desktop will restart automatically
echo.
echo METHOD 2: Using winget (Command Line)
echo.
echo    1. Open PowerShell as Administrator
echo    2. Run: winget upgrade Docker.DockerDesktop
echo    3. Restart Docker Desktop after update
echo.
echo METHOD 3: Manual Download
echo.
echo    1. Visit: https://www.docker.com/products/docker-desktop/
echo    2. Download latest version for Windows
echo    3. Run the installer
echo    4. Follow installation prompts
echo.
echo ========================================
echo.
echo Would you like to open Docker Desktop Settings now? (Y/N)
set /p open_settings="   Enter choice: "
if /i "%open_settings%"=="Y" (
    echo    Opening Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    timeout /t 3 /nobreak >nul
    echo    ✅ Docker Desktop should be opening...
    echo    Please navigate to Settings ^> Software Updates to check for updates.
) else (
    echo    Please update Docker Desktop using one of the methods above.
)

echo.
echo ========================================
echo   After Updating Docker Desktop
echo ========================================
echo.
echo 1. Verify update:
echo    docker --version
echo    docker-compose --version
echo.
echo 2. Restart your HMS containers:
echo    docker-compose down
echo    docker-compose up -d
echo.
echo 3. Check status:
echo    docker-compose ps
echo.
echo ========================================
echo.
pause
