@echo off
echo ========================================
echo Complete Test Suite - Front Desk Payer Selection
echo ========================================
echo.

echo Step 1: Activating virtual environment...
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo Virtual environment activated
) else if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
    echo Virtual environment activated
) else (
    echo WARNING: No virtual environment found
    echo Continuing without venv...
)
echo.

echo Step 2: Running Python tests...
python TEST_PAYER_SELECTION.ps1 2>nul || powershell -ExecutionPolicy Bypass -File TEST_PAYER_SELECTION.ps1
echo.

echo Step 3: Quick form import test...
python -c "from hospital.forms import PatientForm; f = PatientForm(); print('✓ Form created successfully'); print('✓ Fields:', len(f.fields), 'total'); print('✓ payer_type field exists:', 'payer_type' in f.fields)"
echo.

echo Step 4: Checking view imports...
python -c "from hospital.views import patient_create; print('✓ View imports OK')"
echo.

echo ========================================
echo All Tests Complete!
echo ========================================
echo.
echo Ready to start server and test in browser.
echo Run: python manage.py runserver
echo Then visit: http://127.0.0.1:8000/hms/patients/create/
echo.
pause

