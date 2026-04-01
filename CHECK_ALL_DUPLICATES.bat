@echo off
echo.
echo ========================================
echo   Comprehensive Duplicate Check
echo   Checks ALL types of duplicates
echo ========================================
echo.

REM Check if Docker is running
echo [1/2] Checking Docker Desktop...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo    ⚠️  Docker Desktop is not running
    echo    Checking if running locally...
    goto :local_check
) else (
    echo    ✅ Docker Desktop is running
    goto :docker_check
)

:docker_check
echo.
echo [2/2] Running comprehensive duplicate check in Docker...
docker-compose exec -T web python manage.py check_all_duplicates
if %errorlevel% neq 0 (
    echo    ❌ Check failed!
    pause
    exit /b 1
)
goto :end

:local_check
echo.
echo [2/2] Running comprehensive duplicate check locally...
python manage.py check_all_duplicates
if %errorlevel% neq 0 (
    echo    ❌ Check failed!
    pause
    exit /b 1
)

:end
echo.
echo ========================================
echo   ✅ CHECK COMPLETE!
echo ========================================
echo.
pause




