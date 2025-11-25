@echo off
echo ========================================
echo RESET ALL STAFF PASSWORDS
echo ========================================
echo.
echo This will reset passwords for ALL staff users.
echo.
set /p default_password="Enter default password for all staff (default: staff123): "
if "%default_password%"=="" set default_password=staff123

echo.
echo Resetting all staff passwords to: %default_password%
echo.

docker-compose exec web python reset_all_users_passwords.py %default_password%

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo ✅ ALL STAFF PASSWORDS RESET!
    echo ========================================
    echo.
    echo Default password: %default_password%
    echo.
    echo Staff can now login with their username and this password.
    echo.
) else (
    echo.
    echo ❌ Failed to reset passwords
    echo.
)

pause

