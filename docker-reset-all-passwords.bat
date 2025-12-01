@echo off
REM ========================================
REM 🔄 RESET ALL USER PASSWORDS IN DOCKER
REM ========================================
echo.
echo ========================================
echo   🔄 RESET ALL USER PASSWORDS
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

echo [2/3] Setting default passwords...
echo    This will reset all user passwords to default values.
echo.
set /p confirm="Continue? (y/n): "
if /i not "%confirm%"=="y" (
    echo    Cancelled.
    pause
    exit /b 0
)

echo.
echo [3/3] Resetting passwords...
echo.

REM Reset all passwords
docker-compose exec -T web python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); users = User.objects.all(); count = 0; [setattr(u, 'password', u.set_password('staff123')) or u.save() or setattr(count, '__add__', lambda x: count + 1) for u in users if not u.is_superuser]; admin_users = User.objects.filter(is_superuser=True); [setattr(u, 'password', u.set_password('admin123')) or u.save() or setattr(count, '__add__', lambda x: count + 1) for u in admin_users]; print(f'✅ Reset passwords for {len(users)} users'); print('Default passwords:'); print('  Admin users: admin123'); print('  Staff users: staff123')"

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   ✅ PASSWORDS RESET!
    echo ========================================
    echo.
    echo Default passwords:
    echo    Admin users: admin123
    echo    Staff users: staff123
    echo.
    echo ⚠️  IMPORTANT: Change passwords after first login!
    echo.
) else (
    echo.
    echo ❌ Failed to reset passwords
    echo    Check Docker logs: docker-compose logs web
    echo.
)

pause

