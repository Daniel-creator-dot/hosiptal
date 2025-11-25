@echo off
REM Check Patient Tables - Simple Version

echo ===============================================================
echo     CHECKING PATIENT TABLES
echo ===============================================================
echo.

echo Running database check...
echo.

python manage.py dbshell < check_patient.sql

echo.
echo ===============================================================
echo Check complete!
echo ===============================================================
echo.

pause




















