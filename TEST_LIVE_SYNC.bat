@echo off
echo ======================================================================
echo TESTING LIVE CASHIER TO ACCOUNTING SYNC
echo ======================================================================
echo.
echo This will create a test payment and show you it syncing to accounting
echo.
pause

cd /d "%~dp0"
python test_accounting_sync.py

echo.
echo ======================================================================
echo.
echo Now check Admin to see the synced data:
echo   - http://127.0.0.1:8000/admin/hospital/revenue/
echo   - http://127.0.0.1:8000/admin/hospital/advancedjournalentry/
echo.
pause




















