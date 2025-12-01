@echo off
REM ====================================================================
REM HOSPITAL MANAGEMENT SYSTEM - DATABASE ERROR FIX
REM ====================================================================
echo.
echo ====================================================================
echo DATABASE ERROR FIX UTILITY
echo ====================================================================
echo.

REM Try to find and use Python with Django
echo [Step 1] Checking Python environment...

REM Try .venv first
if exist ".venv\Scripts\python.exe" (
    echo Found .venv, using it...
    set PYTHON_CMD=.venv\Scripts\python.exe
    goto :run_fix
)

REM Try venv
if exist "venv\Scripts\python.exe" (
    echo Found venv, using it...
    set PYTHON_CMD=venv\Scripts\python.exe
    goto :run_fix
)

REM Use system Python
echo Using system Python...
set PYTHON_CMD=python

:run_fix
echo.
echo [Step 2] Checking for database errors...
%PYTHON_CMD% manage.py fix_database --check-only

if errorlevel 1 (
    echo.
    echo ERROR: Could not run database check.
    echo.
    echo This usually means:
    echo 1. Django is not installed - run: pip install -r requirements.txt
    echo 2. Virtual environment is not activated
    echo 3. Database connection is not configured
    echo.
    echo Trying to create and apply migrations anyway...
    echo.
)

echo.
echo [Step 3] Creating missing migrations...
%PYTHON_CMD% manage.py makemigrations hospital

echo.
echo [Step 4] Applying migrations...
%PYTHON_CMD% manage.py migrate

echo.
echo [Step 5] Final verification...
%PYTHON_CMD% manage.py fix_database --check-only

echo.
echo ====================================================================
echo Database fix process complete!
echo ====================================================================
echo.
echo If you see errors above, please:
echo 1. Ensure Django is installed: pip install -r requirements.txt
echo 2. Activate your virtual environment
echo 3. Check your database connection in .env file
echo.
pause

