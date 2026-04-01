@echo off
echo.
echo ========================================
echo   Restart Django and Fix Accounting
echo   Clear Non-Excel Data + Fix Balances
echo ========================================
echo.

REM Step 1: Clear non-Excel data and fix balances
echo [1/4] Clearing non-Excel data and fixing balances...
python clear_non_excel_data_and_fix_balances.py
if %errorlevel% neq 0 (
    echo    ERROR: Failed to clear data and fix balances!
    pause
    exit /b 1
)
echo    [OK] Data cleared and balances fixed
echo.

REM Step 2: Fix General Ledger balance calculations
echo [2/4] Fixing General Ledger balance calculations...
python fix_general_ledger_balance_calculation.py
if %errorlevel% neq 0 (
    echo    ERROR: Failed to fix balance calculations!
    pause
    exit /b 1
)
echo    [OK] Balance calculations fixed
echo.

REM Step 3: Check if Django is running and stop it
echo [3/4] Checking Django processes...
tasklist /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq *manage.py*" 2>nul | find /I "python.exe" >nul
if %errorlevel% == 0 (
    echo    Stopping Django processes...
    taskkill /F /IM python.exe /FI "WINDOWTITLE eq *manage.py*" 2>nul
    timeout /t 2 /nobreak >nul
)
echo    [OK] Django processes checked
echo.

REM Step 4: Restart Django
echo [4/4] Restarting Django server...
echo    Starting server on http://localhost:8000
start "Django Server" cmd /k "python manage.py runserver 0.0.0.0:8000"
timeout /t 5 /nobreak >nul
echo    [OK] Django server started
echo.

echo ========================================
echo   RESTART COMPLETE!
echo ========================================
echo.
echo Changes applied:
echo   - Non-Excel data cleared
echo   - All revenue entries cleared
echo   - General Ledger balances fixed
echo   - Django server restarted
echo.
echo Server: http://localhost:8000
echo.
pause
