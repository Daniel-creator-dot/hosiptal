@echo off
echo.
echo ========================================
echo   Check and Fix All Patients Database
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
docker-compose exec web python manage.py fix_all_patients --dry-run
echo.

echo [3/3] Applying fixes to all patients...
echo    This will:
echo      - Generate MRN for patients missing it
echo      - Fix empty first/last names
echo      - Fix invalid dates of birth
echo      - Normalize phone numbers
echo      - Fix other data issues
echo.
set /p confirm="Continue with fixes? (Y/N): "
if /i not "%confirm%"=="Y" (
    echo    Cancelled.
    pause
    exit /b 0
)

docker-compose exec web python manage.py fix_all_patients --fix-all
echo.

echo ========================================
echo   ✅ PATIENT DATABASE FIXED!
echo ========================================
echo.
pause





