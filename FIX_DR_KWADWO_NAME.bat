@echo off
echo.
echo ========================================
echo   Fix Dr. Kwadwo Ayisi Name Display
echo ========================================
echo.

REM Check if Docker is running
echo [1/2] Checking Docker Desktop...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo    ⚠️  Docker Desktop is not running
    echo    Checking if running locally...
    goto :local_fix
) else (
    echo    ✅ Docker Desktop is running
    goto :docker_fix
)

:docker_fix
echo.
echo [2/2] Fixing name in Docker...
docker-compose exec -T web python manage.py fix_staff_user_name --employee-id SPE-DOC-0001 --first-name Kwadwo --last-name Ayisi
if %errorlevel% neq 0 (
    echo    ❌ Failed to fix name!
    pause
    exit /b 1
)
goto :end

:local_fix
echo.
echo [2/2] Fixing name locally...
python manage.py fix_staff_user_name --employee-id SPE-DOC-0001 --first-name Kwadwo --last-name Ayisi
if %errorlevel% neq 0 (
    echo    ❌ Failed to fix name!
    pause
    exit /b 1
)

:end
echo.
echo ========================================
echo   ✅ COMPLETE!
echo ========================================
echo.
echo The name should now display in the USER column.
echo Refresh the page to see the update.
echo.
pause




