@echo off
echo ========================================
echo CHECKING DATABASE PASSWORD
echo ========================================
echo.

echo Testing different passwords...
echo.

echo [1/4] Testing password: 1993
docker-compose exec -T web python -c "import psycopg2; conn = psycopg2.connect(host='host.docker.internal', port=5432, user='postgres', password='1993', database='postgres'); print('✅ SUCCESS: Password is 1993'); conn.close()" 2>nul
if %errorlevel% equ 0 (
    echo    ✅ Password 1993 works!
    goto :found
)

echo [2/4] Testing password: postgres
docker-compose exec -T web python -c "import psycopg2; conn = psycopg2.connect(host='host.docker.internal', port=5432, user='postgres', password='postgres', database='postgres'); print('✅ SUCCESS: Password is postgres'); conn.close()" 2>nul
if %errorlevel% equ 0 (
    echo    ✅ Password postgres works!
    echo    Updating .env...
    powershell -Command "$content = Get-Content .env -Raw; $content = $content -replace 'DATABASE_URL=postgresql://postgres:[^@]*@', 'DATABASE_URL=postgresql://postgres:postgres@'; $content | Set-Content .env -NoNewline"
    docker-compose restart web
    echo    ✅ Fixed! Restarting services...
    goto :found
)

echo [3/4] Testing password: (empty)
docker-compose exec -T web python -c "import psycopg2; conn = psycopg2.connect(host='host.docker.internal', port=5432, user='postgres', password='', database='postgres'); print('✅ SUCCESS: No password needed'); conn.close()" 2>nul
if %errorlevel% equ 0 (
    echo    ✅ No password needed!
    echo    Updating .env...
    powershell -Command "$content = Get-Content .env -Raw; $content = $content -replace 'DATABASE_URL=postgresql://postgres:[^@]*@', 'DATABASE_URL=postgresql://postgres@'; $content | Set-Content .env -NoNewline"
    docker-compose restart web
    echo    ✅ Fixed! Restarting services...
    goto :found
)

echo [4/4] Testing password: PASSWORD
docker-compose exec -T web python -c "import psycopg2; conn = psycopg2.connect(host='host.docker.internal', port=5432, user='postgres', password='PASSWORD', database='postgres'); print('✅ SUCCESS: Password is PASSWORD'); conn.close()" 2>nul
if %errorlevel% equ 0 (
    echo    ✅ Password PASSWORD works!
    echo    Updating .env...
    powershell -Command "$content = Get-Content .env -Raw; $content = $content -replace 'DATABASE_URL=postgresql://postgres:[^@]*@', 'DATABASE_URL=postgresql://postgres:PASSWORD@'; $content | Set-Content .env -NoNewline"
    docker-compose restart web
    echo    ✅ Fixed! Restarting services...
    goto :found
)

echo.
echo ❌ None of the tested passwords worked.
echo.
echo You need to find your PostgreSQL password:
echo   1. Open pgAdmin
echo   2. Try to connect to PostgreSQL server
echo   3. Enter the password that works
echo   4. That's your password!
echo   5. Run: FIX_POSTGRESQL_PASSWORD.bat
echo   6. Choose option 2 and enter that password
echo.
goto :end

:found
echo.
echo ========================================
echo ✅ PASSWORD FOUND AND FIXED!
echo ========================================
echo.
echo Waiting for services to restart...
timeout /t 5 /nobreak >nul
echo.
echo Testing database connection...
docker-compose exec -T web python manage.py dbshell -c "\conninfo" 2>nul
if %errorlevel% equ 0 (
    echo.
    echo ✅ Database connection working!
) else (
    echo.
    echo ⚠️  Connection test failed, but password was updated.
    echo    Try accessing: http://192.168.0.102:8000
)
echo.

:end
pause














