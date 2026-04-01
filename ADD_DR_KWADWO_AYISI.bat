@echo off
echo.
echo ========================================
echo   Add Dr. Kwadwo Ayisi - Medical Director
echo ========================================
echo.

REM Check if Docker is running
echo [1/2] Checking Docker Desktop...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo    ⚠️  Docker Desktop is not running
    echo    Checking if running locally...
    goto :local_add
) else (
    echo    ✅ Docker Desktop is running
    goto :docker_add
)

:docker_add
echo.
echo [2/2] Adding Dr. Kwadwo Ayisi in Docker...
docker-compose exec -T web python manage.py add_medical_director_kwadwo
if %errorlevel% neq 0 (
    echo    ❌ Failed to add staff member!
    pause
    exit /b 1
)
goto :end

:local_add
echo.
echo [2/2] Adding Dr. Kwadwo Ayisi locally...
python manage.py add_medical_director_kwadwo
if %errorlevel% neq 0 (
    echo    ❌ Failed to add staff member!
    pause
    exit /b 1
)

:end
echo.
echo ========================================
echo   ✅ COMPLETE!
echo ========================================
echo.
pause




