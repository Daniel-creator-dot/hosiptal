@echo off
echo ========================================
echo Quick Server Restart
echo ========================================
echo.

REM Try to use venv if it exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

echo Starting server...
echo.
echo Access at: http://127.0.0.1:8000
echo Test: http://127.0.0.1:8000/hms/patients/create/
echo.
echo Press Ctrl+C to stop
echo.

python manage.py runserver 127.0.0.1:8000

pause

