@echo off
echo ========================================
echo Starting Django Server with HTTPS
echo ========================================
echo.
echo This enables camera access from network machines
echo.

REM Check if django-extensions is installed
python -c "import django_extensions" 2>nul
if errorlevel 1 (
    echo Installing django-extensions...
    pip install django-extensions
)

REM Check if certificate exists
if not exist "certs\server.crt" (
    echo.
    echo Certificate not found. Generating...
    echo.
    python setup_https_simple.py
    echo.
)

REM Start server with HTTPS
echo Starting server on https://0.0.0.0:8000
echo.
echo Access from other machines: https://YOUR_IP:8000
echo (Replace YOUR_IP with your server's IP address)
echo.
echo Browser will show security warning - click Advanced and Proceed
echo.
python manage.py runserver_plus --cert-file certs/server.crt --key-file certs/server.key 0.0.0.0:8000
pause
