@echo off
echo ================================================================================
echo PROFESSIONAL CONSULTATION PRICE IMPORT
echo ================================================================================
echo.
echo This will import all consultation prices from Excel into the database.
echo.
pause

python manage.py import_consultation_prices --verbose

echo.
echo ================================================================================
echo IMPORT COMPLETE
echo ================================================================================
echo.
echo You can now view prices at: http://127.0.0.1:8000/hms/pricing/
echo.
pause








