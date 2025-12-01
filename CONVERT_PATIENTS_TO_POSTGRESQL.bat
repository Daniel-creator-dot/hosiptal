@echo off
echo.
echo ========================================
echo   Convert Patient Data to PostgreSQL
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
docker-compose exec web python manage.py convert_patients_to_postgresql --dry-run
echo.

echo [3/3] Converting patient data to PostgreSQL format...
echo    This will:
echo      - Fix encoding issues
echo      - Fix date format issues
echo      - Normalize NULL values
echo      - Ensure PostgreSQL compatibility
echo.
set /p confirm="Continue with conversion? (Y/N): "
if /i not "%confirm%"=="Y" (
    echo    Cancelled.
    pause
    exit /b 0
)

docker-compose exec web python manage.py convert_patients_to_postgresql --fix-all
echo.

echo ========================================
echo   ✅ PATIENT DATA CONVERTED!
echo ========================================
echo.
pause





