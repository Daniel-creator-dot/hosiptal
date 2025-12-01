@echo off
echo ========================================
echo ENSURING DOCKER DESKTOP AUTO-START
echo ========================================
echo.

echo This script will:
echo 1. Configure Docker Desktop to start on boot
echo 2. Ensure HMS services start after Docker Desktop
echo.

REM Check if Docker Desktop settings file exists
set DOCKER_SETTINGS=%APPDATA%\Docker\settings.json

if exist "%DOCKER_SETTINGS%" (
    echo Found Docker Desktop settings file.
    echo.
    echo Please enable auto-start manually:
    echo 1. Open Docker Desktop
    echo 2. Click Settings (gear icon)
    echo 3. Go to "General" tab
    echo 4. Check "Start Docker Desktop when you log in"
    echo 5. Click "Apply & Restart"
    echo.
) else (
    echo Docker Desktop settings file not found.
    echo Docker Desktop may not be installed or configured.
    echo.
)

echo Opening Docker Desktop for you...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe" 2>nul
if errorlevel 1 (
    start "" "%ProgramFiles(x86)%\Docker\Docker\Docker Desktop.exe" 2>nul
)

echo.
echo ========================================
echo HMS AUTO-START STATUS
echo ========================================
echo.

REM Check if startup shortcut exists
set STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set STARTUP_SHORTCUT=%STARTUP_FOLDER%\HMS_AutoStart.lnk

if exist "%STARTUP_SHORTCUT%" (
    echo ✅ HMS startup shortcut exists
) else (
    echo ⚠️  HMS startup shortcut missing
    echo    Creating it now...
    powershell -ExecutionPolicy Bypass -File setup_docker_autostart.ps1
)

echo.
echo ========================================
echo SETUP COMPLETE!
echo ========================================
echo.
echo Next steps:
echo 1. In Docker Desktop (opening now):
echo    Settings -^> General -^> Check "Start Docker Desktop when you log in"
echo.
echo 2. Restart your computer to test
echo.
echo 3. After restart, wait 2-3 minutes, then check:
echo    docker-compose ps
echo.
pause














