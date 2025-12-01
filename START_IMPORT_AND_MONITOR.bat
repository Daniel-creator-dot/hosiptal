@echo off
echo ================================================================================
echo     PATIENT DATA IMPORT - BACKGROUND WITH MONITORING
echo ================================================================================
echo.
echo This will:
echo   ✓ Start import in background
echo   ✓ Monitor progress every 30 seconds  
echo   ✓ Show patient count updates
echo   ✓ Notify when complete
echo.
echo Estimated time: 5-10 minutes
echo.
pause

python import_patient_with_progress.py

pause


