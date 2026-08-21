@echo off
title HMS - Ensure C:\chm
cd /d C:\chm
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\ensure_c_chm.ps1" -Fix
if errorlevel 1 (
    echo.
    echo HMS could not be verified on C:\chm. See messages above.
    pause
    exit /b 1
)
echo.
pause
