@echo off
echo ========================================
echo FIXING ALLOWED_HOSTS ERROR
echo ========================================
echo.

echo Restarting web service to apply ALLOWED_HOSTS fix...
docker-compose restart web

echo.
echo Waiting for service to restart...
timeout /t 10 /nobreak >nul

echo.
echo ========================================
echo FIX APPLIED!
echo ========================================
echo.
echo The ALLOWED_HOSTS error should now be fixed.
echo.
echo Try accessing again:
echo    http://192.168.0.102:8000
echo.
echo If you still see the error, wait 30 seconds and try again.
echo.
pause














