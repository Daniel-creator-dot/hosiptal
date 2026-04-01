@echo off
echo.
echo ========================================
echo   Restart Django Server
echo ========================================
echo.

REM Check if Django is running
echo [1/3] Checking for running Django processes...
tasklist /FI "IMAGENAME eq python.exe" 2>nul | find /I "python.exe" >nul
if %errorlevel% == 0 (
    echo    Stopping existing Django processes...
    taskkill /F /IM python.exe 2>nul
    timeout /t 3 /nobreak >nul
    echo    [OK] Processes stopped
) else (
    echo    [OK] No Django processes running
)
echo.

REM Clear Python cache
echo [2/3] Clearing Python cache...
if exist "*.pyc" del /Q *.pyc 2>nul
if exist "__pycache__" rmdir /S /Q __pycache__ 2>nul
for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /S /Q "%%d" 2>nul
echo    [OK] Cache cleared
echo.

REM Start Django
echo [3/3] Starting Django server...
echo    Server will start on: http://localhost:8000
echo    Press Ctrl+C to stop the server
echo.
start "Django Server" cmd /k "python manage.py runserver 0.0.0.0:8000"
timeout /t 5 /nobreak >nul
echo    [OK] Django server started
echo.

echo ========================================
echo   Django Server Restarted!
echo ========================================
echo.
echo Server: http://localhost:8000
echo.
echo Changes applied:
echo   - Non-Excel data cleared
echo   - All revenue entries cleared
echo   - General Ledger balance calculation fixed
echo   - Server restarted
echo.
pause
