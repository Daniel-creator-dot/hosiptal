@echo off
echo ========================================
echo Simple Test Server - Quick Start
echo ========================================
echo.

echo Installing Django...
python -m pip install django django-crispy-forms --quiet --user

echo.
echo Creating test .env file...
(
    echo SECRET_KEY=test-key-12345
    echo DEBUG=True
    echo ALLOWED_HOSTS=localhost,127.0.0.1
    echo DATABASE_URL=sqlite:///test_db.sqlite3
) > .env.test

echo.
echo Starting server with test settings...
echo.
echo ========================================
echo Server will start at:
echo   http://127.0.0.1:8000
echo.
echo Test feature at:
echo   http://127.0.0.1:8000/hms/patients/create/
echo.
echo Press Ctrl+C to stop
echo ========================================
echo.

REM Temporarily override DATABASE_URL for testing
set DATABASE_URL=sqlite:///test_db.sqlite3
python manage.py runserver 127.0.0.1:8000

pause

