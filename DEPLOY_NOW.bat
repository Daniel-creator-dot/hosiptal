@echo off
REM Quick deployment script for Windows
REM This will copy files and provide commands to run on remote server

echo ==========================================
echo Drug Accountability System Deployment
echo ==========================================
echo.

REM Set your server details here
set SERVER=user@192.168.2.216
set REMOTE_PATH=/app/hospital
set REMOTE_PROJECT=/app

echo Step 1: Copying files to remote server...
echo.

scp hospital/urls.py %SERVER%:%REMOTE_PATH%/urls.py
if errorlevel 1 (
    echo ERROR: Failed to copy urls.py
    pause
    exit /b 1
)

scp hospital/views_drug_accountability.py %SERVER%:%REMOTE_PATH%/views_drug_accountability.py
if errorlevel 1 (
    echo ERROR: Failed to copy views_drug_accountability.py
    pause
    exit /b 1
)

scp hospital/views_departments.py %SERVER%:%REMOTE_PATH%/views_departments.py
if errorlevel 1 (
    echo ERROR: Failed to copy views_departments.py
    pause
    exit /b 1
)

scp hospital/models_drug_accountability.py %SERVER%:%REMOTE_PATH%/models_drug_accountability.py
if errorlevel 1 (
    echo ERROR: Failed to copy models_drug_accountability.py
    pause
    exit /b 1
)

scp hospital/migrations/1058_add_drug_accountability_system.py %SERVER%:%REMOTE_PATH%/migrations/1058_add_drug_accountability_system.py
if errorlevel 1 (
    echo ERROR: Failed to copy migration file
    pause
    exit /b 1
)

scp hospital/templates/hospital/pharmacy_dashboard_worldclass.html %SERVER%:%REMOTE_PATH%/templates/hospital/pharmacy_dashboard_worldclass.html
if errorlevel 1 (
    echo ERROR: Failed to copy template
    pause
    exit /b 1
)

echo.
echo ==========================================
echo Files copied successfully!
echo ==========================================
echo.
echo Next: SSH into your server and run:
echo.
echo   ssh %SERVER%
echo   cd %REMOTE_PROJECT%
echo   python manage.py migrate hospital 1058_add_drug_accountability_system
echo   python manage.py runserver 0.0.0.0:8000
echo.
echo Or run this command to execute migration remotely:
echo   ssh %SERVER% "cd %REMOTE_PROJECT% && python manage.py migrate hospital 1058_add_drug_accountability_system"
echo.
pause







