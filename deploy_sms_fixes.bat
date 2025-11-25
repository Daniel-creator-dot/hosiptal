@echo off
REM Deployment script for SMS fixes on Windows
REM Run this on the server after uploading code

echo ============================================================
echo DEPLOYING SMS FIXES TO SERVER
echo ============================================================

REM 1. Run migrations
echo.
echo [1] Running database migrations...
python manage.py migrate --noinput

REM 2. Collect static files
echo.
echo [2] Collecting static files...
python manage.py collectstatic --noinput

REM 3. Clear all caches
echo.
echo [3] Clearing all caches...
python manage.py clear_all_caches

REM 4. Fix server errors
echo.
echo [4] Checking and fixing server errors...
python manage.py fix_server_errors

REM 5. Test SMS API configuration
echo.
echo [5] Testing SMS API configuration...
python manage.py test_sms_api

REM 6. Check for failed SMS
echo.
echo [6] Checking for failed SMS...
python manage.py check_sms_failures --last-hours 24

echo.
echo ============================================================
echo DEPLOYMENT COMPLETE
echo ============================================================
echo.
echo IMPORTANT: Update SMS_API_KEY if needed:
echo   python manage.py update_sms_api_key YOUR_API_KEY
echo.
echo Then restart the server
echo ============================================================
pause




