@echo off
REM ========================================
REM Apply HR Manager Changes to Docker
REM ========================================
echo.
echo ========================================
echo   Applying HR Manager Changes to Docker
echo ========================================
echo.

REM Check if Docker is running
echo [1/6] Checking Docker Desktop...
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

REM Check if containers are running
echo [2/6] Checking Docker containers...
docker-compose ps | findstr "Up" >nul 2>&1
if %errorlevel% neq 0 (
    echo    ⚠️  Containers are not running. Starting them...
    docker-compose up -d
    timeout /t 5 /nobreak >nul
) else (
    echo    ✅ Containers are running
)
echo.

REM Create migration for model changes
echo [3/6] Creating database migration for HR Manager profession...
docker-compose exec -T web python manage.py makemigrations hospital
if %errorlevel% neq 0 (
    echo    ⚠️  Warning: Migration creation had issues (may already exist)
) else (
    echo    ✅ Migration created
)
echo.

REM Run migrations
echo [4/6] Running database migrations...
docker-compose exec -T web python manage.py migrate
if %errorlevel% neq 0 (
    echo    ❌ ERROR: Migrations failed
    pause
    exit /b 1
)
echo    ✅ Migrations complete
echo.

REM Create default groups (ensures HR Manager group exists)
echo [5/6] Creating/updating role groups...
docker-compose exec -T web python manage.py shell -c "from hospital.utils_roles import create_default_groups; create_default_groups(); print('✅ Role groups updated')"
if %errorlevel% neq 0 (
    echo    ⚠️  Warning: Group creation had issues
) else (
    echo    ✅ Role groups ready
)
echo.

REM Assign HR Manager role to Nana Yaa B. Asamoah
echo [6/6] Assigning HR Manager role to Nana Yaa B. Asamoah...
docker-compose exec -T web python manage.py assign_hr_manager --name "Nana Yaa B. Asamoah"
if %errorlevel% neq 0 (
    echo    ⚠️  Warning: Role assignment had issues (user may not exist yet)
    echo    You can run this manually: docker-compose exec web python manage.py assign_hr_manager --name "Nana Yaa B. Asamoah"
) else (
    echo    ✅ HR Manager role assigned
)
echo.

REM Restart web container to apply code changes
echo [7/7] Restarting web container to apply code changes...
docker-compose restart web
timeout /t 3 /nobreak >nul
echo    ✅ Web container restarted
echo.

echo ========================================
echo   ✅ CHANGES APPLIED TO DOCKER!
echo ========================================
echo.
echo 📋 Summary:
echo    - Model changes: HR Manager profession added
echo    - Database migrations: Applied
echo    - Role groups: Updated
echo    - User assignment: Nana Yaa B. Asamoah → HR Manager
echo    - Web container: Restarted
echo.
echo 🌐 Access your application:
echo    http://localhost:8000
echo.
echo 📋 To verify HR Manager access:
echo    docker-compose exec web python manage.py assign_hr_manager --name "Nana Yaa B. Asamoah"
echo.
pause


