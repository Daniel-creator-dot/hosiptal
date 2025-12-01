@echo off
echo ========================================
echo DUPLICATE PREVENTION FIX - FINAL STEPS
echo ========================================
echo.

echo Step 1: Running migration for database indexes...
python manage.py migrate hospital 1043

echo.
echo Step 2: Checking for existing duplicates...
python manage.py fix_duplicates --dry-run

echo.
echo Step 3: If duplicates found, run this to fix them:
echo    python manage.py fix_duplicates --fix
echo.

echo ========================================
echo FIX COMPLETE!
echo ========================================
echo.
echo The system now has 5 layers of duplicate prevention:
echo 1. Form validation
echo 2. Transaction-based check with row locking
echo 3. Final safety check
echo 4. Database unique constraints
echo 5. Exception handling
echo.
pause

