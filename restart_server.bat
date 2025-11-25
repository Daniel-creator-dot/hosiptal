@echo off
REM Script to restart Django server and clear caches on Windows
echo ============================================================
echo RESTARTING SERVER AND CLEARING CACHES
echo ============================================================
echo.

echo [1/3] Clearing all caches...
python manage.py clear_all_caches
if %errorlevel% neq 0 (
    echo ERROR: Failed to clear caches
    pause
    exit /b 1
)
echo.

echo [2/3] Collecting static files...
python manage.py collectstatic --noinput
if %errorlevel% neq 0 (
    echo WARNING: Static files collection had issues, continuing...
)
echo.

echo [3/3] Starting server...
echo.
echo Server will start on http://127.0.0.1:8000
echo Press Ctrl+C to stop the server
echo.
python manage.py runserver
pause




