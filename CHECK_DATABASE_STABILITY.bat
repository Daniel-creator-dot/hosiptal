@echo off
echo.
echo ========================================
echo   Database Stability Check
echo ========================================
echo.

REM Check if Docker is running
echo [1/3] Checking Docker Desktop...
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
echo [2/3] Running database stability check in Docker...
docker-compose exec -T web python manage.py ensure_database_stability --check-only
if %errorlevel% neq 0 (
    echo    ❌ Check failed!
    pause
    exit /b 1
)
echo    ✅ Check complete
goto :end

:local_check
echo.
echo [2/3] Running database stability check locally...
python manage.py ensure_database_stability --check-only
if %errorlevel% neq 0 (
    echo    ❌ Check failed!
    pause
    exit /b 1
)
echo    ✅ Check complete

:end
echo.
echo [3/3] Summary
echo    Review the output above for any issues.
echo.
echo    To fix issues automatically:
echo      docker-compose exec web python manage.py ensure_database_stability --fix-all
echo.
pause




