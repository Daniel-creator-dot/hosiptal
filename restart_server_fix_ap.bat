@echo off
echo ========================================
echo RESTARTING SERVER TO FIX AP ADD_AMOUNT
echo ========================================
echo.

echo [1/3] Stopping all Python processes...
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul

echo [2/3] Clearing Python cache...
if exist "*.pyc" del /Q *.pyc
if exist "__pycache__" rmdir /S /Q __pycache__
for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /S /Q "%%d"

echo [3/3] Starting Django server...
cd /d d:\chm
start "Django Server" cmd /k "python manage.py runserver 0.0.0.0:8000"

echo.
echo ========================================
echo SERVER RESTARTED!
echo ========================================
echo.
echo The add_amount method should now work.
echo Test it by going to Accounts Payable -> Edit -> Add Amount
echo.
pause
