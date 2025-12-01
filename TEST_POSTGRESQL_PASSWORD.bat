@echo off
echo ========================================
echo TEST POSTGRESQL PASSWORDS
echo ========================================
echo.
echo This will test common passwords to find the correct one.
echo.

REM Test password: postgres
echo Testing password: postgres...
docker-compose exec -T web python -c "import psycopg2; conn = psycopg2.connect(host='host.docker.internal', port=5432, user='postgres', password='postgres', database='postgres'); print('✅ SUCCESS: Password is postgres'); conn.close()" 2>nul
if %errorlevel% equ 0 (
    echo.
    echo ✅ FOUND IT! Password is: postgres
    echo Updating .env...
    powershell -Command "$content = Get-Content .env -Raw; $content = $content -replace 'DATABASE_URL=postgresql://postgres:[^@]*@', 'DATABASE_URL=postgresql://postgres:postgres@'; $content | Set-Content .env -NoNewline"
    docker-compose restart web
    echo.
    echo ✅ Fixed! Services restarted.
    pause
    exit /b 0
)

REM Test password: 1993
echo Testing password: 1993...
docker-compose exec -T web python -c "import psycopg2; conn = psycopg2.connect(host='host.docker.internal', port=5432, user='postgres', password='1993', database='postgres'); print('✅ SUCCESS: Password is 1993'); conn.close()" 2>nul
if %errorlevel% equ 0 (
    echo.
    echo ✅ FOUND IT! Password is: 1993
    echo (Already set in .env)
    docker-compose restart web
    echo.
    echo ✅ Services restarted.
    pause
    exit /b 0
)

REM Test password: (empty)
echo Testing password: (empty)...
docker-compose exec -T web python -c "import psycopg2; conn = psycopg2.connect(host='host.docker.internal', port=5432, user='postgres', password='', database='postgres'); print('✅ SUCCESS: No password needed'); conn.close()" 2>nul
if %errorlevel% equ 0 (
    echo.
    echo ✅ FOUND IT! No password needed
    echo Updating .env...
    powershell -Command "$content = Get-Content .env -Raw; $content = $content -replace 'DATABASE_URL=postgresql://postgres:[^@]*@', 'DATABASE_URL=postgresql://postgres@'; $content | Set-Content .env -NoNewline"
    docker-compose restart web
    echo.
    echo ✅ Fixed! Services restarted.
    pause
    exit /b 0
)

echo.
echo ❌ None of the common passwords worked.
echo.
echo You need to:
echo 1. Open pgAdmin
echo 2. Connect to PostgreSQL (enter your password)
echo 3. That password is what you need
echo 4. Run: FIX_POSTGRESQL_PASSWORD.bat
echo 5. Choose option 2 and enter that password
echo.
pause














