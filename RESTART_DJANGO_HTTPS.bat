@echo off
echo ========================================
echo Restarting Django Server with HTTPS
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

REM Check if certificate exists
if not exist "certs\server.crt" (
    echo.
    echo Certificate not found. Generating...
    python setup_https_simple.py
    echo.
)

REM Start Django server with HTTPS
echo.
echo Starting Django server with HTTPS...
echo Access from network: https://YOUR_IP:8000
echo.
python manage.py runserver_plus --cert-file certs/server.crt --key-file certs/server.key 0.0.0.0:8000

pause
