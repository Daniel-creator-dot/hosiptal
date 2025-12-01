@echo off
echo.
echo ========================================
echo   Create .env File for Single Database
echo ========================================
echo.

if exist .env (
    echo .env file already exists!
    echo.
    set /p overwrite="Overwrite existing .env file? (Y/N): "
    if /i not "!overwrite!"=="Y" (
        echo Cancelled.
        pause
        exit /b 0
    )
)

echo Creating .env file from template...
copy .env.template .env >nul 2>&1

if exist .env (
    echo    ✅ .env file created successfully!
    echo.
    echo The .env file contains:
    echo   - DATABASE_URL=postgresql://hms_user:hms_password@localhost:5432/hms_db
    echo   - All services will use this single database configuration
    echo.
    echo Next steps:
    echo   1. Restart Docker services: docker-compose restart
    echo   2. Verify: ENFORCE_SINGLE_DATABASE.bat
) else (
    echo    ❌ ERROR: Failed to create .env file
    echo    Please create it manually by copying .env.template to .env
)

echo.
pause





