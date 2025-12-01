@echo off
REM ========================================
REM 🔐 CREATE/RESET ADMIN USER IN DOCKER
REM ========================================
echo.
echo ========================================
echo   🔐 CREATE/RESET ADMIN USER
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

REM Get user input
echo [2/3] Admin User Configuration...
set /p username="Enter username (default: admin): "
if "%username%"=="" set username=admin

set /p email="Enter email (default: admin@hospital.com): "
if "%email%"=="" set email=admin@hospital.com

set /p password="Enter password (default: admin123): "
if "%password%"=="" set password=admin123

echo.
echo Creating/resetting user: %username%
echo.

REM Create or update user
echo [3/3] Creating admin user...
docker-compose exec -T web python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); user, created = User.objects.get_or_create(username='%username%', defaults={'email': '%email%', 'is_staff': True, 'is_superuser': True}); user.set_password('%password%'); user.is_staff = True; user.is_superuser = True; user.is_active = True; user.save(); print('✅ Admin user created!' if created else '✅ Admin password reset!'); print(f'Username: %username%'); print(f'Password: %password%')"

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   ✅ ADMIN USER READY!
    echo ========================================
    echo.
    echo Login credentials:
    echo    Username: %username%
    echo    Password: %password%
    echo.
    echo 🌐 Access URLs:
    echo    Admin Panel: http://localhost:8000/admin/
    echo    HMS Login: http://localhost:8000/hms/login/
    echo.
    echo ⚠️  IMPORTANT: Change the password after first login!
    echo.
) else (
    echo.
    echo ❌ Failed to create/reset admin user
    echo    Check Docker logs: docker-compose logs web
    echo.
)

pause

