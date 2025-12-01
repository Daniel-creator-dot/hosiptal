@echo off
echo.
echo ========================================
echo   Check and Fix All Usernames
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

echo [2/3] Running dry-run to check for issues...
docker-compose exec web python manage.py check_all_usernames --dry-run
echo.

echo [3/3] Fixing all username issues...
echo    This will:
echo      - Fix empty usernames
echo      - Fix duplicate usernames
echo      - Fix invalid username formats
echo      - Fix usernames that are too long
echo.
set /p confirm="Continue with fixes? (Y/N): "
if /i not "%confirm%"=="Y" (
    echo    Cancelled.
    pause
    exit /b 0
)

docker-compose exec web python manage.py check_all_usernames --fix-all
echo.

echo ========================================
echo   ✅ ALL USERNAMES FIXED!
echo ========================================
echo.
pause





