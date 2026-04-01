@echo off
echo ============================================================
echo COMPREHENSIVE DUPLICATE FIX - ALL ISSUES
echo ============================================================
echo.
echo This will:
echo   1. Check for existing duplicates
echo   2. Remove all duplicates
echo   3. Verify no duplicates remain
echo.
echo ============================================================
echo.

echo Step 1: Checking for duplicates (dry run)...
python manage.py remove_all_duplicates --dry-run

echo.
echo ============================================================
echo.
set /p proceed="Found duplicates above? Remove them now? (yes/no): "
if /i "%proceed%"=="yes" (
    echo.
    echo Removing all duplicates...
    python manage.py remove_all_duplicates
    echo.
    echo ============================================================
    echo Verifying no duplicates remain...
    echo ============================================================
    python manage.py remove_all_duplicates --dry-run
    echo.
    echo ============================================================
    echo DUPLICATE FIX COMPLETE!
    echo ============================================================
    echo.
    echo All duplicates have been removed.
    echo The system now has 6 layers of duplicate protection:
    echo   1. JavaScript - Prevents double-submission
    echo   2. Form Validation - Checks before submission
    echo   3. View Validation - Transaction-based checks
    echo   4. API Validation - Serializer checks
    echo   5. Model Save - Final safety net
    echo   6. Database Constraints - Unique constraints
    echo.
) else (
    echo.
    echo Duplicate removal cancelled.
    echo You can run this script again later.
)

echo.
pause






