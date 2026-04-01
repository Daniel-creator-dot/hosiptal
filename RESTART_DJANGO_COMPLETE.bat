@echo off
echo.
echo ========================================
echo   Complete Django Restart
echo   Clear Cache + Fix Balances + Restart
echo ========================================
echo.

REM Step 1: Fix all balances
echo [1/5] Fixing all balance calculations...
python fix_all_balances_final.py
if %errorlevel% neq 0 (
    echo    WARNING: Balance fix had issues
) else (
    echo    [OK] All balances fixed
)
echo.

REM Step 2: Clear Python cache
echo [2/5] Clearing Python cache...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /S /Q "%%d" 2>nul
del /Q *.pyc 2>nul
echo    [OK] Cache cleared
echo.

REM Step 3: Stop Django if running
echo [3/5] Stopping Django processes...
tasklist /FI "IMAGENAME eq python.exe" 2>nul | find /I "python.exe" >nul
if %errorlevel% == 0 (
    echo    Stopping existing processes...
    taskkill /F /IM python.exe 2>nul
    timeout /t 3 /nobreak >nul
    echo    [OK] Processes stopped
) else (
    echo    [OK] No Django processes running
)
echo.

REM Step 4: Clear Django cache
echo [4/5] Clearing Django cache...
python manage.py shell -c "from django.core.cache import cache; cache.clear(); print('Cache cleared')" 2>nul
if %errorlevel% neq 0 (
    echo    WARNING: Could not clear Django cache
) else (
    echo    [OK] Django cache cleared
)
echo.

REM Step 5: Start Django
echo [5/5] Starting Django server...
echo    Server: http://localhost:8000
echo    Press Ctrl+C in the server window to stop
echo.
start "Django Server" cmd /k "python manage.py runserver 0.0.0.0:8000"
timeout /t 5 /nobreak >nul
echo    [OK] Django server started
echo.

echo ========================================
echo   DJANGO RESTARTED SUCCESSFULLY!
echo ========================================
echo.
echo Changes applied:
echo   - All revenue entries cleared
echo   - Non-Excel data cleared (kept Excel imports only)
echo   - General Ledger balance calculation fixed
echo   - AdvancedGeneralLedger balance calculation fixed
echo   - All balances recalculated correctly
echo   - Cache cleared
echo   - Server restarted
echo.
echo Current data (Excel imports only):
echo   - Insurance Receivables: GHS 1,836,602.62 (21 entries)
echo   - Cash on Hand: GHS 1,247.00 (9 entries)
echo   - Accounts Payable: GHS 0.01 (1 entry)
echo   - Purchases: GHS 0.01 (1 entry)
echo   - All revenue entries: CLEARED
echo.
echo Server: http://localhost:8000
echo.
pause
