@echo off
echo ========================================
echo Quick Local Start - SQLite (No Docker)
echo ========================================
echo.

echo Step 1: Installing Django (if needed)...
python -m pip install django --quiet 2>nul
python -m pip install django-crispy-forms --quiet 2>nul
echo.

echo Step 2: Setting up SQLite database...
if not exist db.sqlite3 (
    echo Creating SQLite database...
    python manage.py migrate --run-syncdb --noinput 2>nul
) else (
    echo Database exists, running migrations...
    python manage.py migrate --noinput 2>nul
)
echo.

echo Step 3: Starting server...
echo.
echo ========================================
echo Server Starting...
echo ========================================
echo.
echo Access at: http://127.0.0.1:8000
echo.
echo To test payer selection feature:
echo   http://127.0.0.1:8000/hms/patients/create/
echo.
echo Press Ctrl+C to stop
echo.
echo ========================================
echo.

REM Temporarily use SQLite for quick testing
set DJANGO_SETTINGS_MODULE=hms.settings
python manage.py runserver 127.0.0.1:8000

pause

