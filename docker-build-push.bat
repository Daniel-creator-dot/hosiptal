@echo off
REM ========================================
REM 🐳 DOCKER BUILD & PUSH TO DOCKER HUB
REM ========================================
echo.
echo ========================================
echo   🐳 HMS DOCKER BUILD & PUSH
echo ========================================
echo.

REM Check if Docker is running
echo [1/4] Checking Docker Desktop...
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
echo [2/4] Docker Hub Configuration...
set /p DOCKER_USERNAME="Enter your Docker Hub username: "
if "%DOCKER_USERNAME%"=="" (
    echo    ❌ ERROR: Docker Hub username is required!
    pause
    exit /b 1
)

REM Set image name and tag
set IMAGE_NAME=%DOCKER_USERNAME%/hms
set TAG=latest
set FULL_IMAGE=%IMAGE_NAME%:%TAG%

echo    Image: %FULL_IMAGE%
echo.

REM Login to Docker Hub
echo [3/4] Logging into Docker Hub...
docker login
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Failed to login to Docker Hub!
    pause
    exit /b 1
)
echo    ✅ Logged in successfully
echo.

REM Build the image
echo [4/4] Building Docker image...
echo    This may take several minutes...
docker build -t %FULL_IMAGE% .
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Failed to build Docker image!
    pause
    exit /b 1
)
echo    ✅ Build complete
echo.

REM Push the image
echo [5/5] Pushing to Docker Hub...
echo    This may take several minutes depending on your connection...
docker push %FULL_IMAGE%
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Failed to push Docker image!
    pause
    exit /b 1
)
echo    ✅ Push complete
echo.

echo ========================================
echo   ✅ SUCCESS!
echo ========================================
echo.
echo 🐳 Your image is now available at:
echo    https://hub.docker.com/r/%DOCKER_USERNAME%/hms
echo.
echo 📋 To run this image:
echo    docker run -p 8000:8000 %FULL_IMAGE%
echo.
echo    Or use docker-compose.yml with:
echo    docker-compose up -d
echo.
pause

