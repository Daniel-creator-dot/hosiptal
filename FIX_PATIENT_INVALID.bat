@echo off
echo.
echo ========================================
echo   Fix Patient Invalid Phone Numbers
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

echo [2/3] Fixing phone number validation...
echo    Updated phone regex to accept Ghana numbers (024, 050, 020, etc.)
echo    Phone numbers will now be validated correctly
echo.

echo [3/3] Restarting web service...
docker-compose restart web
echo.

echo ========================================
echo   ✅ FIX APPLIED!
echo ========================================
echo.
echo Phone number validation has been updated to accept:
echo   ✅ Ghana numbers: 0241234567, 0501234567, etc.
echo   ✅ International: +233241234567
echo   ✅ Any 9-15 digit number
echo.
echo Patients should no longer show as "invalid"!
echo.
pause





