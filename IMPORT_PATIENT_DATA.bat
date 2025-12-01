@echo off
echo ================================================================================
echo     IMPORTING PATIENT DATA INTO POSTGRESQL
echo ================================================================================
echo.
echo This will import ~35,000 patient records from patient_data.sql
echo.
echo IMPORTANT: This process will take 5-10 minutes. DO NOT CLOSE THIS WINDOW!
echo.
echo Progress will be shown below...
echo.
echo ================================================================================
echo.

docker-compose exec web python manage.py import_legacy_database --tables patient_data --sql-dir import/legacy --skip-drop

echo.
echo ================================================================================
echo     IMPORT COMPLETE!
echo ================================================================================
echo.
echo Verifying import...
docker-compose exec web python manage.py check_patient_database

echo.
echo ================================================================================
echo     NEXT STEPS
echo ================================================================================
echo.
echo 1. View patients at: http://127.0.0.1:8000/hms/patients/
echo 2. Use "Source" filter and select "Imported Legacy"
echo 3. Click "Search" to see all imported patients
echo.
pause


