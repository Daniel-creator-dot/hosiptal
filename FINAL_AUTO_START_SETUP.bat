@echo off
echo ========================================
echo FINAL AUTO-START SETUP
echo ========================================
echo.

echo [1/3] Checking HMS startup shortcut...
set STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set STARTUP_SHORTCUT=%STARTUP_FOLDER%\HMS_AutoStart.lnk

if exist "%STARTUP_SHORTCUT%" (
    echo    ✅ HMS startup shortcut exists
) else (
    echo    Creating HMS startup shortcut...
    powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%STARTUP_SHORTCUT%'); $Shortcut.TargetPath = '%~dp0startup_hms.bat'; $Shortcut.WorkingDirectory = '%~dp0'; $Shortcut.Description = 'HMS Docker Services Auto-Start'; $Shortcut.WindowStyle = 1; $Shortcut.Save()"
    echo    ✅ Created
)
echo.

echo [2/3] Checking Docker Desktop auto-start...
echo    Opening Docker Desktop settings...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe" 2>nul
if errorlevel 1 (
    start "" "%ProgramFiles(x86)%\Docker\Docker\Docker Desktop.exe" 2>nul
)
timeout /t 3 /nobreak >nul
echo.
echo    ⚠️  IMPORTANT: In Docker Desktop:
echo       1. Click Settings (gear icon)
echo       2. Go to "General" tab
echo       3. Check "Start Docker Desktop when you log in"
echo       4. Click "Apply & Restart"
echo.

echo [3/3] Verifying configuration...
echo.
echo ✅ HMS startup script: startup_hms.bat
echo ✅ Startup shortcut: %STARTUP_SHORTCUT%
if exist "%STARTUP_SHORTCUT%" (
    echo    Status: EXISTS ✅
) else (
    echo    Status: MISSING ❌
)
echo.

echo ========================================
echo SETUP COMPLETE!
echo ========================================
echo.
echo What happens on boot:
echo   1. Windows starts
echo   2. Docker Desktop starts (if enabled)
echo   3. HMS startup script runs
echo   4. Script waits for Docker Desktop
echo   5. HMS services start automatically
echo   6. Server ready at http://192.168.0.102:8000
echo.
echo To test: Restart your computer
echo.
pause














