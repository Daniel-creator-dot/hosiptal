@echo off
REM ================================================================
REM Quick Server Deployment Fix (Windows)
REM Run this before deploying or after copying to server
REM ================================================================

echo ================================================================
echo   Quick Server Deployment Fix
echo ================================================================
echo.

echo Step 1: Creating required directories...
if not exist staticfiles mkdir staticfiles
if not exist media mkdir media
if not exist media\patient_profiles mkdir media\patient_profiles
if not exist media\documents mkdir media\documents
if not exist media\uploads mkdir media\uploads
if not exist logs mkdir logs
echo [OK] Directories created
echo.

echo Step 2: Running pre-deployment checks...
python server_deployment_fixes.py
echo.

echo Step 3: Fixing deployment errors...
python fix_server_deployment_errors.py
echo.

echo ================================================================
echo   Fix Complete!
echo ================================================================
echo.
echo Next steps:
echo 1. Upload files to server
echo 2. On server, run: ./fix_server_deployment.sh
echo 3. Configure web server (Nginx/Apache)
echo 4. Start services
echo.
pause



