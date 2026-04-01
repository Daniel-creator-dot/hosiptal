@echo off
echo ============================================================
echo START DATABASE AND FIX DUPLICATES
echo ============================================================
echo.

echo Step 1: Starting Docker database...
docker-compose up -d db

echo.
echo Waiting for database to be ready...
timeout /t 10 /nobreak >nul

echo.
echo Step 2: Checking for duplicates (dry run)...
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
) else (
    echo.
    echo Duplicate removal cancelled.
)

echo.
pause






