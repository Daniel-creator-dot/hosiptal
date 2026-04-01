@echo off
REM ================================================================
REM Simple PostgreSQL Fix - Uses pgAdmin instructions
REM ================================================================

echo ================================================================
echo   Fix PostgreSQL Authentication - Simple Method
echo ================================================================
echo.
echo This script will guide you through fixing PostgreSQL using pgAdmin.
echo.
echo STEP 1: Open pgAdmin
echo ----------------------------------------
echo 1. Open pgAdmin from Start Menu
echo    (Search for "pgAdmin" or "PostgreSQL")
echo.
echo STEP 2: Connect to PostgreSQL Server
echo ----------------------------------------
echo 1. In pgAdmin, expand your PostgreSQL server
echo 2. Enter the password when prompted
echo    (This is the password you set during PostgreSQL installation)
echo.
echo STEP 3: Create User and Set Password
echo ----------------------------------------
echo 1. Expand "Login/Group Roles" in left sidebar
echo 2. Check if "hms_user" exists:
echo    - If EXISTS: Right-click "hms_user" ^> Properties ^> Definition tab ^> Set password to: hms_password ^> Save
echo    - If NOT EXISTS: Right-click "Login/Group Roles" ^> Create ^> Login/Group Role
echo      * General tab: Name = hms_user
echo      * Definition tab: Password = hms_password
echo      * Privileges tab: Check "Can login?"
echo      * Click Save
echo.
echo STEP 4: Create Database
echo ----------------------------------------
echo 1. Right-click "Databases" ^> Create ^> Database
echo 2. Name: hms_db
echo 3. Owner: hms_user (or postgres)
echo 4. Click Save
echo.
echo STEP 5: Grant Privileges (if owner is postgres)
echo ----------------------------------------
echo 1. Right-click "hms_db" database ^> Query Tool
echo 2. Run these commands:
echo.
echo    GRANT ALL ON SCHEMA public TO hms_user;
echo    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO hms_user;
echo    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO hms_user;
echo.
echo STEP 6: Test Connection
echo ----------------------------------------
echo After completing above steps, test with:
echo   python manage.py migrate
echo.
echo ================================================================
echo.
echo Press any key when you've completed the steps above...
pause >nul
echo.
echo Testing database connection...
python manage.py migrate --dry-run 2>nul
if errorlevel 1 (
    echo.
    echo [WARNING] Connection test failed. Please verify:
    echo 1. PostgreSQL service is running
    echo 2. User hms_user exists with password hms_password
    echo 3. Database hms_db exists
    echo 4. .env file has: DATABASE_URL=postgresql://hms_user:hms_password@localhost:5432/hms_db
    echo.
) else (
    echo.
    echo [SUCCESS] Database connection looks good!
    echo You can now run: python manage.py migrate
    echo.
)
pause



