@echo off
REM Quick start with SQLite for testing UI changes
echo ========================================
echo Quick Start - SQLite Database
echo ========================================
echo.

REM Install minimal requirements
echo Installing Django...
python -m pip install django django-crispy-forms --quiet

REM Create .env with SQLite if it doesn't exist
if not exist .env (
    echo Creating .env file with SQLite...
    (
        echo SECRET_KEY=test-secret-key-for-local-testing-only
        echo DEBUG=True
        echo ALLOWED_HOSTS=localhost,127.0.0.1
        echo DATABASE_URL=sqlite:///db.sqlite3
    ) > .env
)

echo.
echo Running migrations...
python manage.py migrate --noinput 2>nul

echo.
echo ========================================
echo Starting Server
echo ========================================
echo.
echo Open: http://127.0.0.1:8000/hms/patients/create/
echo.
echo Press Ctrl+C to stop
echo.

python manage.py runserver 127.0.0.1:8000

pause

