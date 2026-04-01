@echo off
echo ========================================
echo Restarting Django Server
echo ========================================
echo.

REM Kill all Python processes running Django
echo Stopping existing Django servers...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *runserver*" 2>nul
taskkill /F /IM python.exe /FI "COMMANDLINE eq *manage.py*" 2>nul
timeout /t 2 /nobreak >nul

REM Alternative: Kill by port (more reliable)
echo Checking port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    echo Killing process on port 8000: %%a
    taskkill /F /PID %%a 2>nul
)
timeout /t 2 /nobreak >nul

REM Start Django server
echo.
echo Starting Django server...
echo.
python manage.py runserver 0.0.0.0:8000

pause
