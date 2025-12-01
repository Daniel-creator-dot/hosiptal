@echo off
REM ========================================
REM 🚀 RUN HMS FROM DOCKER HUB
REM ========================================
echo.
echo ========================================
echo   🚀 HMS DOCKER RUN
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

REM Get Docker Hub username
echo [2/3] Docker Image Configuration...
set /p DOCKER_USERNAME="Enter your Docker Hub username (or 'local' to use local image): "
if "%DOCKER_USERNAME%"=="" (
    echo    Using local image...
    set IMAGE_NAME=hms
) else if "%DOCKER_USERNAME%"=="local" (
    echo    Using local image...
    set IMAGE_NAME=hms
) else (
    set IMAGE_NAME=%DOCKER_USERNAME%/hms
)

set TAG=latest
set FULL_IMAGE=%IMAGE_NAME%:%TAG%

echo    Image: %FULL_IMAGE%
echo.

REM Check if image exists locally, if not pull it
if not "%DOCKER_USERNAME%"=="local" (
    echo [3/3] Checking for image...
    docker images %FULL_IMAGE% | findstr /C:"%IMAGE_NAME%" >nul 2>&1
    if %errorlevel% neq 0 (
        echo    Image not found locally. Pulling from Docker Hub...
        docker pull %FULL_IMAGE%
        if %errorlevel% neq 0 (
            echo    ❌ ERROR: Failed to pull Docker image!
            echo    Make sure you've pushed the image first using docker-build-push.bat
            pause
            exit /b 1
        )
        echo    ✅ Image pulled successfully
    ) else (
        echo    ✅ Image found locally
    )
) else (
    echo [3/3] Using local image...
)

echo.
echo ========================================
echo   🚀 STARTING HMS CONTAINER
echo ========================================
echo.

REM Stop and remove existing container if it exists
docker stop hms-container 2>nul
docker rm hms-container 2>nul

REM Run the container
echo Starting container...
docker run -d ^
    --name hms-container ^
    -p 8000:8000 ^
    -e DATABASE_URL=postgresql://hms_user:hms_password@host.docker.internal:5432/hms_db ^
    -e REDIS_URL=redis://host.docker.internal:6379/0 ^
    -e SECRET_KEY=your-secret-key-change-this ^
    -e DEBUG=True ^
    -e ALLOWED_HOSTS=* ^
    %FULL_IMAGE%

if %errorlevel% neq 0 (
    echo    ❌ ERROR: Failed to start container!
    pause
    exit /b 1
)

echo    ✅ Container started successfully
echo.
echo ========================================
echo   ✅ HMS IS RUNNING!
echo ========================================
echo.
echo 🌐 Access your application:
echo    http://localhost:8000
echo.
echo 📋 Useful Commands:
echo    View logs: docker logs -f hms-container
echo    Stop: docker stop hms-container
echo    Remove: docker rm hms-container
echo    Restart: docker restart hms-container
echo.
echo ⚠️  NOTE: Make sure PostgreSQL and Redis are running!
echo    Use docker-compose up -d to start all services
echo.
pause

