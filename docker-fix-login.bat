@echo off
REM ========================================
REM 🔐 FIX LOGIN ISSUES - DOCKER VERSION
REM ========================================
echo.
echo ========================================
echo   🔐 FIX LOGIN ISSUES
echo ========================================
echo.

REM Check if Docker is running
echo [1/4] Checking Docker Desktop...
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

REM Check if web container is running
docker ps --format "{{.Names}}" | findstr /i "web" >nul 2>&1
if %errorlevel% neq 0 (
    echo    ⚠️  Web container is not running!
    echo    Starting containers...
    docker-compose up -d
    echo    Waiting for services to start...
    timeout /t 15 /nobreak >nul
    echo.
)

echo [2/4] Creating/Resetting admin user...
docker-compose exec -T web python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); user, created = User.objects.get_or_create(username='admin', defaults={'email': 'admin@hospital.com', 'is_staff': True, 'is_superuser': True}); user.set_password('admin123'); user.is_staff = True; user.is_superuser = True; user.is_active = True; user.save(); print('✅ Admin user ready!')"
echo.

echo [3/4] Unlocking all accounts...
docker-compose exec -T web python manage.py shell -c "from hospital.models_login_attempts import LoginAttempt; LoginAttempt.objects.all().update(is_locked=False, failed_attempts=0); print('✅ All accounts unlocked')" 2>nul
if %errorlevel% neq 0 (
    echo    ⚠️  Could not unlock accounts (may not exist yet)
)
echo.

echo [4/4] Activating all users...
docker-compose exec -T web python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.all().update(is_active=True); print('✅ All users activated')"
echo.

echo ========================================
echo   ✅ LOGIN ISSUES FIXED!
echo ========================================
echo.
echo Default Admin Credentials:
echo    Username: admin
echo    Password: admin123
echo.
echo 🌐 Access URLs:
echo    Admin Panel: http://localhost:8000/admin/
echo    HMS Login: http://localhost:8000/hms/login/
echo.
echo ⚠️  IMPORTANT: Change the password after first login!
echo.
pause

