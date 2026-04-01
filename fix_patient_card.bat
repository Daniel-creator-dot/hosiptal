@echo off
echo ========================================
echo Patient Card Deep Fix - Running Now...
echo ========================================
echo.

cd /d %~dp0

echo [1/4] Clearing Python cache...
for /d /r hospital %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
for /r hospital %%f in (*.pyc) do @if exist "%%f" del /q "%%f"
echo ✓ Python cache cleared
echo.

echo [2/4] Clearing template cache...
python manage.py clear_template_cache
echo ✓ Template cache cleared
echo.

echo [3/4] Checking Django configuration...
python manage.py check
echo ✓ Django check complete
echo.

echo [4/4] Verifying template exists...
if exist "hospital\templates\hospital\patient_qr_card.html" (
    echo ✓ Template file exists
) else (
    echo ✗ Template file NOT found!
)
echo.

echo ========================================
echo Fix Complete!
echo ========================================
echo.
echo NEXT STEPS:
echo 1. Restart Django server:
echo    - Press Ctrl+C in server terminal
echo    - Run: python manage.py runserver
echo.
echo 2. Test patient card:
echo    - Go to: http://localhost:8000/hms/patients/
echo    - Click any patient
echo    - Add /qr-card/ to URL
echo.
echo 3. Hard refresh browser: Ctrl + Shift + R
echo.
pause




