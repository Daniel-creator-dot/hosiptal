@echo off
echo ================================================================================
echo     MONITORING PATIENT DATA IMPORT STATUS
echo ================================================================================
echo.

:loop
echo [%time%] Checking import status...
echo.

docker-compose exec db psql -U hms_user -d hms_db -c "SELECT COUNT(*) as patient_count FROM patient_data;" 2>nul

if %errorlevel% equ 0 (
    echo.
    echo ✅ Import appears to be working!
    echo.
    timeout /t 10 /nobreak >nul
    goto loop
) else (
    echo.
    echo ⏳ Import in progress or table not created yet...
    echo.
    timeout /t 10 /nobreak >nul
    goto loop
)


