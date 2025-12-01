@echo off
echo ========================================
echo GRANTING ACCOUNTANT FINANCIAL ACCESS
echo ========================================
echo.
echo This will grant all accountants access to all financial models in Django admin.
echo.

docker-compose exec web python manage.py grant_accountant_admin_access --all-accountants

if %errorlevel% equ 0 (
    echo.
    docker-compose exec web python grant_all_financial_permissions.py
    echo.
    echo ========================================
    echo ✅ ACCOUNTANT ACCESS GRANTED!
    echo ========================================
    echo.
    echo IMPORTANT: Accountants need to LOG OUT and LOG BACK IN
    echo for the permissions to take effect!
    echo.
) else (
    echo.
    echo ❌ Error granting access
    echo.
)

pause














