@echo off
echo ================================================================================
echo PROFESSIONAL CONSULTATION PRICE IMPORT - DOCKER
echo ================================================================================
echo.

REM Find container name
for /f "tokens=*" %%i in ('docker ps --format "{{.Names}}" ^| findstr /i "web hms django"') do set CONTAINER_NAME=%%i

if "%CONTAINER_NAME%"=="" (
    echo ERROR: Could not find running container
    echo Please ensure Docker containers are running
    pause
    exit /b 1
)

echo Found container: %CONTAINER_NAME%
echo.

echo Starting import...
echo.

REM Run import with verbose output
docker exec -it %CONTAINER_NAME% python manage.py import_consultation_prices --verbose

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ================================================================================
    echo IMPORT COMPLETE!
    echo ================================================================================
    echo.
    echo View prices at: http://localhost:8000/hms/pricing/
    echo.
) else (
    echo.
    echo ================================================================================
    echo IMPORT FAILED
    echo ================================================================================
    echo.
    echo Please check the error messages above
    echo.
)

pause








