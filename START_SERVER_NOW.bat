@echo off
echo ========================================
echo Starting HMS Server - Quick Start
echo ========================================
echo.

REM Try to activate venv if it exists
if exist .venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo No virtual environment found - using system Python
)

echo.
echo Starting Django development server...
echo.
echo Server will be available at:
echo   http://127.0.0.1:8000
echo   http://localhost:8000
echo.
echo Press Ctrl+C to stop the server
echo.
echo ========================================
echo.

python manage.py runserver 127.0.0.1:8000

pause
