@echo off
echo ========================================
echo Starting HMS Local Server
echo ========================================
echo.

REM Check if virtual environment exists
if not exist venv\Scripts\activate.bat (
    echo WARNING: Virtual environment not found!
    echo Continuing without virtual environment...
    echo.
    goto :start_server
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

:start_server
echo.
echo Checking database connection...
python manage.py check --database default 2>nul
if errorlevel 1 (
    echo.
    echo WARNING: Database connection check failed!
    echo Attempting to start PostgreSQL container...
    docker-compose up -d db
    echo.
    echo Waiting 5 seconds for database to start...
    timeout /t 5 /nobreak >nul
)

echo.
echo Running migrations...
python manage.py migrate --noinput

echo.
echo ========================================
echo Starting Django Development Server
echo ========================================
echo.
echo Server will be available at:
echo   - http://localhost:8000
echo   - http://127.0.0.1:8000
echo.
echo Press Ctrl+C to stop the server
echo.
echo ========================================
echo.

python manage.py runserver 0.0.0.0:8000

pause
