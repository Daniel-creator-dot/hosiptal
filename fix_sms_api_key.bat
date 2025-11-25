@echo off
REM Quick fix script for SMS API key on Windows
echo ============================================================
echo FIX SMS API KEY
echo ============================================================
echo.
echo Current API key is INVALID (Error Code 1004)
echo.
echo To fix:
echo 1. Get your valid API key from SMS Notify GH dashboard
echo 2. Run this command:
echo    python manage.py update_sms_api_key YOUR_API_KEY_HERE
echo.
echo Or set environment variable:
echo    set SMS_API_KEY=YOUR_API_KEY_HERE
echo.
echo After updating, restart the server and test:
echo    python manage.py test_sms_api
echo    python manage.py check_sms_failures --retry
echo.
echo ============================================================
pause




