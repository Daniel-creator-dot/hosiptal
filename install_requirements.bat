@echo off
REM Install PostgreSQL Python Driver for HMS

echo ===============================================================================
echo           Install PostgreSQL Driver (psycopg2)
echo ===============================================================================
echo.
echo This will install the psycopg2-binary package required for PostgreSQL
echo.

echo Installing psycopg2-binary...
pip install psycopg2-binary

if errorlevel 1 (
    echo.
    echo [ERROR] Installation failed!
    echo.
    echo Trying alternative method...
    pip install psycopg2
    
    if errorlevel 1 (
        echo.
        echo [ERROR] Still failed!
        echo.
        echo Please try manually:
        echo   pip install psycopg2-binary
        echo.
        pause
        exit /b 1
    )
)

echo.
echo [SUCCESS] PostgreSQL driver installed!
echo.
echo You can now:
echo   1. Test connection: python test_db_connection.py
echo   2. Run migrations: python manage.py migrate
echo.
pause

