@echo off
echo ========================================
echo HMS Server - Complete Setup
echo ========================================
echo.

REM Check if running as admin
net session >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Running as Administrator - Configuring Firewall...
    echo.
    
    REM Delete existing rule if it exists
    netsh advfirewall firewall delete rule name="HMS Port 8000" >nul 2>&1
    
    REM Add firewall rule
    netsh advfirewall firewall add rule name="HMS Port 8000" dir=in action=allow protocol=TCP localport=8000
    
    if %errorlevel% equ 0 (
        echo ✅ Firewall configured successfully!
    ) else (
        echo ⚠️  Warning: Failed to configure firewall
    )
    echo.
) else (
    echo ⚠️  WARNING: Not running as Administrator
    echo.
    echo Firewall configuration requires admin rights.
    echo The server will start, but network access may be blocked.
    echo.
    echo To fix: Right-click this file -^> Run as administrator
    echo.
    pause
)

echo ========================================
echo Starting Server
echo ========================================
echo.
echo Server will be accessible at:
echo   - Local: http://127.0.0.1:8000
echo   - Network: http://192.168.0.105:8000
echo.
echo A new window will open with the server.
echo Close that window to stop the server.
echo.
echo ========================================
echo.

REM Start server in new window
start "HMS Server - Port 8000" cmd /k "python manage.py runserver 0.0.0.0:8000"

echo.
echo ✅ Server is starting in a new window!
echo.
echo Check the new window for:
echo   "Starting development server at http://0.0.0.0:8000/"
echo.
echo You can now:
echo   1. Test local: http://127.0.0.1:8000/hms/
echo   2. Test network: http://192.168.0.105:8000/hms/
echo.
echo Press any key to close this window (server will keep running)...
pause >nul






