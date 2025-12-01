@echo off
echo ========================================
echo RESTORE STAFF AND PATIENT DATA
echo ========================================
echo.
echo This will restore your staff and patient data from backup.
echo.

REM Check if backup exists
if not exist "backups\database\db_auto_backup_20251111_215301.sqlite3" (
    echo ERROR: Backup file not found!
    echo Expected: backups\database\db_auto_backup_20251111_215301.sqlite3
    echo.
    echo Please check if the backup file exists.
    pause
    exit /b 1
)

echo Found backup: db_auto_backup_20251111_215301.sqlite3
echo.

echo Starting data restoration...
echo.

docker-compose exec web python restore_staff_and_patients.py

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo ✅ DATA RESTORED SUCCESSFULLY!
    echo ========================================
    echo.
    echo Your staff and patient data has been restored.
    echo.
) else (
    echo.
    echo ❌ Error restoring data
    echo.
)

pause














