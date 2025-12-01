@echo off
echo ========================================
echo Fixing Environment and Starting Server
echo ========================================
echo.

echo Step 1: Fixing pip...
python -m ensurepip --upgrade
echo.

echo Step 2: Installing Django and dependencies...
python -m pip install --upgrade pip
python -m pip install django djangorestframework django-cors-headers django-extensions django-filter crispy-forms
echo.

echo Step 3: Checking installation...
python -c "import django; print('Django version:', django.get_version())"
if errorlevel 1 (
    echo ERROR: Django installation failed!
    pause
    exit /b 1
)
echo.

echo Step 4: Starting server...
echo.
echo ========================================
echo Server Starting...
echo ========================================
echo.
echo Access at: http://127.0.0.1:8000
echo Test feature: http://127.0.0.1:8000/hms/patients/create/
echo.
echo Press Ctrl+C to stop
echo.
python manage.py runserver 127.0.0.1:8000

pause

