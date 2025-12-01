@echo off
echo.
echo ========================================
echo   Grant Bulk SMS Access to User
echo ========================================
echo.

REM Check if Docker is running
echo [1/2] Checking Docker Desktop...
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

REM Grant access
echo [2/2] Granting bulk SMS access to user 'min'...
echo.
docker-compose exec web python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); user = User.objects.filter(username='min').first(); user.is_staff = True; user.save(); print('✅ User min now has bulk SMS access (is_staff=True)')"

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   ✅ ACCESS GRANTED!
    echo ========================================
    echo.
    echo User 'min' can now access bulk SMS features!
    echo.
    echo Access URLs:
    echo   - Bulk SMS Dashboard: http://localhost:8000/hms/sms/bulk/dashboard/
    echo   - From Reception Dashboard: Click "Bulk SMS" button
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





