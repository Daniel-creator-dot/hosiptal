@echo off
echo.
echo ========================================
echo   Import Patient Portal Data
echo   Creates Patients with QR Codes
echo ========================================
echo.

REM Check if Docker is running
echo [1/3] Checking Docker Desktop...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Docker Desktop is not running!
    echo    Please start Docker Desktop and try again.
    echo.
    pause
    exit /b 1
)
echo    ✅ Docker Desktop is running
echo.

REM Check if SQL files exist
echo [2/3] Checking SQL files...
set SQL_DIR=f:\
set FILES_FOUND=0

if exist "%SQL_DIR%patient_portal_menu.sql" (
    echo    ✅ patient_portal_menu.sql
    set /a FILES_FOUND+=1
) else (
    echo    ❌ patient_portal_menu.sql not found
)

if exist "%SQL_DIR%patient_reminders.sql" (
    echo    ✅ patient_reminders.sql
    set /a FILES_FOUND+=1
) else (
    echo    ❌ patient_reminders.sql not found
)

if exist "%SQL_DIR%patient_access_offsite.sql" (
    echo    ✅ patient_access_offsite.sql
    set /a FILES_FOUND+=1
) else (
    echo    ❌ patient_access_offsite.sql not found
)

if exist "%SQL_DIR%patient_access_onsite.sql" (
    echo    ✅ patient_access_onsite.sql
    set /a FILES_FOUND+=1
) else (
    echo    ❌ patient_access_onsite.sql not found
)

echo.
if %FILES_FOUND% equ 0 (
    echo    ⚠️  No SQL files found in %SQL_DIR%
    echo    Please ensure SQL files are in the correct location
    echo.
    pause
    exit /b 1
)

echo    Found %FILES_FOUND% SQL files
echo.

REM Run import
echo [3/3] Importing patient portal data...
echo.
docker-compose exec web python manage.py import_patient_portal_data --sql-dir "%SQL_DIR%"

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   ✅ IMPORT COMPLETE!
    echo ========================================
    echo.
    echo Patients have been created with QR codes!
    echo.
    echo Next steps:
    echo   1. View patients: http://localhost:8000/hms/patients/
    echo   2. View QR codes: Click on any patient, then "QR Card"
    echo   3. Update patient details if you have patient_data table
    echo.
) else (
    echo.
    echo ========================================
    echo   ❌ IMPORT FAILED!
    echo ========================================
    echo.
    echo Check the error messages above.
    echo.
)

pause





