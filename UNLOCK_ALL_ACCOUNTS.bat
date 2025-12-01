@echo off
echo.
echo ========================================
echo   UNLOCK ALL BLOCKED ACCOUNTS
echo ========================================
echo.

REM Check if Docker is running
echo [1/2] Checking Docker Desktop...
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

REM Run unlock command
echo [2/2] Unlocking all accounts...
echo.
docker-compose exec web python manage.py unlock_all_accounts

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   ✅ ALL ACCOUNTS UNLOCKED!
    echo ========================================
    echo.
    echo All users can now login!
    echo.
) else (
    echo.
    echo ========================================
    echo   ❌ FAILED TO UNLOCK ACCOUNTS
    echo ========================================
    echo.
    echo Check the error messages above.
    echo.
)

pause










