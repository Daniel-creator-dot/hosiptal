@echo off
REM Import Patient Data - Quick Import Script

echo ===============================================================
echo     PATIENT DATA IMPORT
echo ===============================================================
echo.

echo Found 7 patient-related tables:
echo   - patient_data (main patient records)
echo   - patient_reminders
echo   - patient_tracker
echo   - patient_tracker_element
echo   - patient_access_onsite
echo   - patient_access_offsite
echo   - patient_portal_menu
echo.

set /p confirm="Import patient tables now? (Y/N): "
if /i not "%confirm%"=="Y" (
    echo Import cancelled.
    pause
    exit /b
)

echo.
echo Starting import...
echo.

python manage.py import_legacy_database --tables patient_data patient_reminders patient_tracker patient_tracker_element patient_access_onsite patient_access_offsite patient_portal_menu --skip-drop --sql-dir "C:\Users\user\Videos\DS"

echo.
echo ===============================================================
echo Import complete!
echo ===============================================================
echo.
echo Next steps:
echo 1. Check data: python manage.py dbshell
echo    Then type: SELECT COUNT(*) FROM patient_data;
echo.
echo 2. Validate: python manage.py validate_import
echo.
echo 3. View in admin: python manage.py runserver
echo.

pause




















