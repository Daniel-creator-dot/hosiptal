@echo off
echo.
echo ========================================
echo   Create User 'min' with Bulk SMS Access
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

REM Check if user exists
echo [2/3] Checking if user 'min' exists...
docker-compose exec web python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); user = User.objects.filter(username='min').first(); print('EXISTS' if user else 'NOT_EXISTS')" > temp_check.txt 2>&1
findstr /C:"EXISTS" temp_check.txt >nul
if %errorlevel% equ 0 (
    echo    ✅ User 'min' already exists
    echo.
    echo [3/3] Granting bulk SMS access...
    docker-compose exec web python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); user = User.objects.get(username='min'); user.is_staff = True; user.save(); print('✅ User min now has bulk SMS access (is_staff=True)')"
) else (
    echo    ⚠️  User 'min' does not exist
    echo.
    echo [3/3] Creating user 'min' with bulk SMS access...
    echo.
    set /p password="Enter password for user 'min': "
    if "%password%"=="" (
        echo    Using default password: min123
        set password=min123
    )
    docker-compose exec web python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); user, created = User.objects.get_or_create(username='min', defaults={'email': 'min@hospital.com', 'is_staff': True, 'is_active': True}); user.set_password('%password%'); user.is_staff = True; user.is_active = True; user.save(); print('✅ User min created with bulk SMS access!' if created else '✅ User min updated with bulk SMS access!')"
)
del temp_check.txt 2>nul

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   ✅ SUCCESS!
    echo ========================================
    echo.
    echo User 'min' can now access bulk SMS features!
    echo.
    echo Access URLs:
    echo   - Bulk SMS Dashboard: http://localhost:8000/hms/sms/bulk/dashboard/
    echo   - From Reception Dashboard: Click "Bulk SMS" button
    echo.
    echo Login with:
    echo   Username: min
    echo   Password: (the password you set)
    echo.
) else (
    echo.
    echo ========================================
    echo   ❌ FAILED!
    echo ========================================
    echo.
    echo Check the error messages above.
    echo.
)

pause





