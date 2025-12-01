@echo off
echo ====================================================================
echo HOSPITAL MANAGEMENT SYSTEM - DATABASE ERROR FIX
echo ====================================================================
echo.

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo Virtual environment not found, using system Python...
)

echo.
echo [1/3] Checking for database errors...
python manage.py fix_database --check-only

echo.
echo [2/3] Creating missing migrations...
python manage.py makemigrations hospital

echo.
echo [3/3] Applying migrations...
python manage.py migrate

echo.
echo [4/4] Final verification...
python manage.py fix_database --check-only

echo.
echo ====================================================================
echo Database fix complete!
echo ====================================================================
pause

