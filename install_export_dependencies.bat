@echo off
REM Install dependencies for patient export functionality

echo ===============================================================
echo     INSTALLING EXPORT DEPENDENCIES
echo ===============================================================
echo.

echo Installing openpyxl (for Excel export)...
pip install openpyxl

echo.
echo Installing reportlab (for PDF export)...
pip install reportlab

echo.
echo ===============================================================
echo Installation complete!
echo ===============================================================
echo.

pause




















