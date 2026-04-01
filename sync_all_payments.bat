@echo off
echo ================================================================================
echo PROFESSIONAL PAYMENT SYNCHRONIZATION
echo ================================================================================
echo.
echo This will sync ALL payments to the accounting system.
echo.
pause

docker exec chm-web-1 python manage.py sync_all_payments --verbose

echo.
echo ================================================================================
echo SYNCHRONIZATION COMPLETE
echo ================================================================================
echo.
echo View synchronized data at:
echo   - Revenue: http://192.168.2.216:8000/admin/hospital/revenue/
echo   - Receipt Vouchers: http://192.168.2.216:8000/admin/hospital/receiptvoucher/
echo   - Journal Entries: http://192.168.2.216:8000/admin/hospital/advancedjournalentry/
echo.
pause








