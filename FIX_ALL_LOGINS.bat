@echo off
echo.
echo ========================================
echo   Fix All Login Issues
echo   Unlock Accounts, Activate Users
echo ========================================
echo.

REM Check if Docker is running
echo [1/3] Checking Docker Desktop...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Docker Desktop is not running!
    echo    Please start Docker Desktop and try again.
    echo.
    pause
    exit /b 1
)
echo    ✅ Docker Desktop is running
echo.

echo [2/3] Fixing all login issues...
docker-compose exec web python manage.py fix_all_logins --create-superuser
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Failed to fix login issues
    echo.
    pause
    exit /b 1
)
echo.

echo [3/3] Verifying login system...
docker-compose exec web python manage.py shell -c "from django.contrib.auth import get_user_model; from hospital.models_login_attempts import LoginAttempt; User = get_user_model(); print('Users:', User.objects.count()); print('Active:', User.objects.filter(is_active=True).count()); print('Superusers:', User.objects.filter(is_superuser=True).count()); print('Locked attempts:', LoginAttempt.objects.filter(is_locked=True).count())"
echo.

echo ========================================
echo   ✅ Login Issues Fixed!
echo ========================================
echo.
echo Default superuser credentials:
echo   Username: admin
echo   Password: admin123
echo.
echo Please change the password after first login!
echo.
pause





