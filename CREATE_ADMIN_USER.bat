@echo off
echo ========================================
echo CREATE/RESET ADMIN USER
echo ========================================
echo.

echo This will create or reset the admin user.
echo.

set /p username="Enter username (default: admin): "
if "%username%"=="" set username=admin

set /p email="Enter email (default: admin@hospital.com): "
if "%email%"=="" set email=admin@hospital.com

set /p password="Enter password (default: admin123): "
if "%password%"=="" set password=admin123

echo.
echo Creating/resetting user: %username%
echo Email: %email%
echo.

docker-compose exec web python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); user, created = User.objects.get_or_create(username='%username%', defaults={'email': '%email%', 'is_staff': True, 'is_superuser': True}); user.set_password('%password%'); user.is_staff = True; user.is_superuser = True; user.is_active = True; user.save(); print('✅ User created!' if created else '✅ User password updated!'); print(f'Username: {user.username}'); print(f'Email: {user.email}'); print(f'Is Staff: {user.is_staff}'); print(f'Is Superuser: {user.is_superuser}')"

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo ✅ ADMIN USER READY!
    echo ========================================
    echo.
    echo Login credentials:
    echo    Username: %username%
    echo    Password: %password%
    echo.
    echo Access: http://192.168.0.102:8000/hms/login/
    echo.
) else (
    echo.
    echo ❌ Failed to create user
    echo.
)

pause














