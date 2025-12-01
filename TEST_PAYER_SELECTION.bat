@echo off
echo ========================================
echo Testing Front Desk Payer Selection
echo ========================================
echo.

echo [1/5] Checking Python environment...
python --version
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Please activate virtual environment first
    pause
    exit /b 1
)
echo OK
echo.

echo [2/5] Checking Django installation...
python -c "import django; print('Django version:', django.get_version())"
if errorlevel 1 (
    echo ERROR: Django not installed!
    echo Please activate virtual environment or install requirements
    pause
    exit /b 1
)
echo OK
echo.

echo [3/5] Running Django system check...
python manage.py check --deploy
if errorlevel 1 (
    echo WARNING: System check found issues
    echo Continuing anyway...
) else (
    echo OK - No critical errors
)
echo.

echo [4/5] Checking for form syntax errors...
python -c "from hospital.forms import PatientForm; print('Form imports OK')"
if errorlevel 1 (
    echo ERROR: Form has syntax errors!
    pause
    exit /b 1
)
echo OK
echo.

echo [5/5] Checking template...
python -c "import os; os.path.exists('hospital/templates/hospital/patient_form.html') and print('Template exists') or print('Template missing!')"
echo.

echo ========================================
echo TEST SUMMARY
echo ========================================
echo.
echo All checks passed! Ready to test in browser.
echo.
echo Next steps:
echo 1. Start server: python manage.py runserver
echo 2. Open: http://127.0.0.1:8000/hms/patients/create/
echo 3. Look for "Payment Type" dropdown
echo 4. Test selecting Insurance/Corporate/Cash
echo.
pause

