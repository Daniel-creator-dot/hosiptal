@echo off
REM ================================================================
REM PostgreSQL Setup Script for HMS (Windows)
REM ================================================================

echo ========================================
echo   HMS PostgreSQL Setup
echo ========================================
echo.

echo Step 1: Creating PostgreSQL Database and User...
echo.

REM Note: Make sure PostgreSQL is installed and pg commands are in PATH
REM Download from: https://www.postgresql.org/download/windows/

psql -U postgres -c "CREATE DATABASE hms_db;"
psql -U postgres -c "CREATE USER hms_user WITH PASSWORD 'hms_password';"
psql -U postgres -c "ALTER ROLE hms_user SET client_encoding TO 'utf8';"
psql -U postgres -c "ALTER ROLE hms_user SET default_transaction_isolation TO 'read committed';"
psql -U postgres -c "ALTER ROLE hms_user SET timezone TO 'UTC';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE hms_db TO hms_user;"
psql -U postgres -d hms_db -c "GRANT ALL ON SCHEMA public TO hms_user;"

echo.
echo ========================================
echo   PostgreSQL Database Created!
echo ========================================
echo.
echo Database: hms_db
echo User: hms_user
echo Password: hms_password
echo Host: localhost
echo Port: 5432
echo.
echo Next Steps:
echo 1. Update your .env file with DATABASE_URL
echo 2. Run: python manage.py migrate
echo 3. Run: python migrate_data.py (to copy from SQLite)
echo.
pause

















