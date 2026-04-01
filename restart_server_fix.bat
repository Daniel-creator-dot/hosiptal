@echo off
echo ========================================
echo   HOSPITAL MANAGEMENT SYSTEM
echo   Server Restart and Fix Script
echo ========================================
echo.

cd /d d:\chm

echo [1/5] Checking for existing Python processes...
tasklist | findstr "python.exe" >nul
if %errorlevel% == 0 (
    echo Found Python processes running
    echo Stopping existing Python processes...
    taskkill /F /IM python.exe >nul 2>&1
    timeout /t 2 /nobreak >nul
)

echo [2/5] Checking port 8000...
netstat -ano | findstr ":8000.*LISTENING" >nul
if %errorlevel% == 0 (
    echo Port 8000 is in use
    echo Attempting to free port 8000...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do (
        echo Killing process %%a on port 8000...
        taskkill /F /PID %%a >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
)

echo [3/5] Running Django system check...
python manage.py check
if %errorlevel% neq 0 (
    echo ERROR: System check failed!
    pause
    exit /b 1
)

echo [4/5] Clearing caches...
python manage.py clear_all_caches >nul 2>&1

echo [5/5] Starting Django server...
echo.
echo ========================================
echo   Server starting on:
echo   - http://localhost:8000/hms/
echo   - http://127.0.0.1:8000/hms/
echo ========================================
echo.
echo Press Ctrl+C to stop the server
echo.

python manage.py runserver 0.0.0.0:8000

pause
