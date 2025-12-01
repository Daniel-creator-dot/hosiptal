@echo off
echo ========================================
echo PostgreSQL Connection Test
echo ========================================
echo.
echo Testing connection to PostgreSQL Desktop...
echo.

docker-compose exec web python create_postgresql_db.py

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo SUCCESS! Database ready!
    echo ========================================
    echo.
    echo Running migrations...
    docker-compose exec web python manage.py migrate
    echo.
    echo ========================================
    echo Setup Complete!
    echo ========================================
    echo.
    echo Access your application: http://localhost:8000
) else (
    echo.
    echo ========================================
    echo CONNECTION FAILED
    echo ========================================
    echo.
    echo The password "PASSWORD" appears to be incorrect.
    echo.
    echo To fix this:
    echo.
    echo Option 1: Reset PostgreSQL password
    echo   1. Open pgAdmin
    echo   2. Right-click "postgres" user -^> Properties -^> Password
    echo   3. Set password to: PASSWORD
    echo   4. Click Save
    echo   5. Run this script again
    echo.
    echo Option 2: Update .env with correct password
    echo   1. Edit .env file
    echo   2. Update DATABASE_URL with correct password
    echo   3. Restart: docker-compose restart web
    echo   4. Run this script again
    echo.
    echo Option 3: Create database manually in pgAdmin
    echo   1. Open pgAdmin
    echo   2. Connect to PostgreSQL server
    echo   3. Right-click "Databases" -^> Create -^> Database
    echo   4. Name: hms_db
    echo   5. Owner: postgres
    echo   6. Click Save
    echo   7. Then test: docker-compose exec web python manage.py migrate
    echo.
)

pause















