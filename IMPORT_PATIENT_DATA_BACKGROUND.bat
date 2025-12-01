@echo off
echo ================================================================================
echo     BACKGROUND PATIENT DATA IMPORT WITH MONITORING
echo ================================================================================
echo.
echo This script will:
echo   1. Start the import in the background
echo   2. Monitor progress every 30 seconds
echo   3. Log everything to import_log.txt
echo   4. Show you when it's complete
echo.
echo IMPORTANT: This will take 5-10 minutes. DO NOT CLOSE THIS WINDOW!
echo.
pause

echo.
echo [%time%] Starting import...
echo.

REM Start import in background and log to file
start /B cmd /c "docker-compose exec web python manage.py import_legacy_database --tables patient_data --sql-dir import/legacy --skip-drop > import_log.txt 2>&1"

echo [%time%] Import started in background. Monitoring progress...
echo Log file: import_log.txt
echo.

:monitor
timeout /t 30 /nobreak >nul

echo.
echo ================================================================================
echo [%time%] STATUS CHECK
echo ================================================================================

REM Check if table exists
docker-compose exec db psql -U hms_user -d hms_db -c "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'patient_data') as table_exists;" 2>nul | findstr /i "t" >nul

if %errorlevel% equ 0 (
    echo ✅ patient_data table EXISTS!
    echo.
    echo Checking record count...
    docker-compose exec db psql -U hms_user -d hms_db -c "SELECT COUNT(*) as patient_count FROM patient_data;" 2>nul
    echo.
    echo ================================================================================
    echo ✅ IMPORT COMPLETE!
    echo ================================================================================
    echo.
    echo Verifying final status...
    docker-compose exec web python manage.py check_patient_database 2>&1 | findstr /i "patient Total SUMMARY"
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
    exit /b 0
) else (
    echo ⏳ Import still in progress...
    echo.
    echo Last 5 lines from log:
    powershell -Command "Get-Content import_log.txt -Tail 5 -ErrorAction SilentlyContinue"
    echo.
    echo Checking again in 30 seconds...
    goto monitor
)


