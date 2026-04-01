@echo off
echo ============================================================
echo COMPREHENSIVE DUPLICATE REMOVAL
echo ============================================================
echo.
echo This script will find and remove ALL duplicates from your system.
echo.
echo Step 1: Checking for duplicates (dry run)...
echo.
python manage.py remove_all_duplicates --dry-run
echo.
echo.
echo ============================================================
echo If duplicates were found above, you can remove them now.
echo ============================================================
echo.
set /p confirm="Do you want to remove all duplicates? (yes/no): "
if /i "%confirm%"=="yes" (
    echo.
    echo Removing duplicates...
    python manage.py remove_all_duplicates
    echo.
    echo ============================================================
    echo Duplicate removal complete!
    echo ============================================================
) else (
    echo.
    echo Duplicate removal cancelled.
)
echo.
pause






