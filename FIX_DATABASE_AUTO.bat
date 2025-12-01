@echo off
echo ====================================================================
echo HOSPITAL MANAGEMENT SYSTEM - AUTOMATIC DATABASE FIX
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
echo Running comprehensive database fix...
python manage.py fix_database --fix-migrations --fix-constraints

echo.
echo ====================================================================
echo Database fix complete! Check output above for any issues.
echo ====================================================================
pause

