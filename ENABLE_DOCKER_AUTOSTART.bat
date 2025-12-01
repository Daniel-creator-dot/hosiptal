@echo off
REM Simple script to enable Docker Desktop auto-start
echo ========================================
echo Enable Docker Desktop Auto-Start
echo ========================================
echo.
echo This will open Docker Desktop settings.
echo.
echo Please:
echo 1. Go to Settings (gear icon)
echo 2. Click "General" tab
echo 3. Check "Start Docker Desktop when you log in"
echo 4. Click "Apply & Restart"
echo.
echo Press any key to open Docker Desktop...
pause >nul

REM Try to open Docker Desktop
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
timeout /t 2 /nobreak >nul

REM Alternative path
if not exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
    start "" "${ProgramFiles(x86)}\Docker\Docker\Docker Desktop.exe"
)

echo.
echo Docker Desktop should be opening now.
echo Please enable auto-start in settings as described above.
echo.
pause














