@echo off
echo ========================================
echo SETUP ROLE-BASED DASHBOARDS
echo ========================================
echo.
echo This will assign roles to all users based on their profession.
echo.

docker-compose exec web python setup_all_user_roles.py

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo ✅ ROLES ASSIGNED!
    echo ========================================
    echo.
    echo All users will now be redirected to their role-specific dashboards.
    echo.
) else (
    echo.
    echo ❌ Error assigning roles
    echo.
)

pause














