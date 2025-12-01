@echo off
echo.
echo ========================================
echo   Check and Fix All Staff Usernames
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
docker-compose exec web python manage.py fix_staff_usernames --dry-run
echo.

echo [3/3] Fixing all staff username issues...
echo    This will:
echo      - Create user accounts for staff without users
echo      - Fix duplicate usernames
echo      - Fix invalid username formats
echo      - Fix empty usernames
echo.
set /p confirm="Continue with fixes? (Y/N): "
if /i not "%confirm%"=="Y" (
    echo    Cancelled.
    pause
    exit /b 0
)

docker-compose exec web python manage.py fix_staff_usernames --fix-all
echo.

echo ========================================
echo   ✅ STAFF USERNAMES FIXED!
echo ========================================
echo.
pause





