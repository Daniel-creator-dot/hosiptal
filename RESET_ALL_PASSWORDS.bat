@echo off
echo.
echo ========================================
echo   Reset All User Passwords
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

echo [2/2] Resetting all user passwords...
echo    This will reset ALL user passwords to: admin123
echo.
set /p confirm="Continue? (Y/N): "
if /i not "%confirm%"=="Y" (
    echo Cancelled.
    pause
    exit /b 0
)

docker-compose exec web python manage.py reset_all_passwords
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Failed to reset passwords
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   ✅ All Passwords Reset!
echo ========================================
echo.
echo Default password for ALL users: admin123
echo.
echo ⚠️  IMPORTANT: Change passwords after first login!
echo.
pause





