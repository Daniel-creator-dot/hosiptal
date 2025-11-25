@echo off
REM Import Patient Data - Quick Fix Script
REM This will import the main patient_data table

echo ================================================================================
echo     IMPORTING PATIENT DATA
echo ================================================================================
echo.

echo This will import the patient_data table from your legacy database.
echo.
echo SQL File Location: C:\Users\user\Videos\DS\patient_data.sql
echo.

pause

echo.
echo Creating backup of database...
if exist db.sqlite3 (
    copy db.sqlite3 db.sqlite3.backup_before_patient >nul 2>&1
    echo Backup created: db.sqlite3.backup_before_patient
) else (
    echo No existing database - will create new one
)

echo.
echo ================================================================================
echo Starting patient data import...
echo ================================================================================
echo.

REM Import patient_data table
python manage.py import_legacy_database --tables patient_data patient_tracker patient_reminders --skip-drop

echo.
echo ================================================================================
echo Verifying import...
echo ================================================================================
echo.

REM Check if data was imported
python -c "import django; import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings'); django.setup(); from django.db import connection; cursor = connection.cursor(); cursor.execute('SELECT COUNT(*) FROM patient_data'); print(f'Patient records imported: {cursor.fetchone()[0]:,}')"

echo.
echo ================================================================================
echo Import Complete!
echo ================================================================================
echo.
echo Next steps:
echo 1. View data: python manage.py dbshell
echo    Then: SELECT * FROM patient_data LIMIT 5;
echo.
echo 2. Verify: python manage.py validate_import
echo.
echo 3. Check in database browser or create admin interface
echo.

pause




















