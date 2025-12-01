@echo off
echo ========================================
echo FIX POSTGRESQL PASSWORD
echo ========================================
echo.
echo The PostgreSQL password in .env doesn't match your PostgreSQL Desktop password.
echo.
echo Option 1: Update PostgreSQL password to match .env
echo Option 2: Update .env with correct PostgreSQL password
echo.
echo Current .env password: postgres
echo.
echo What would you like to do?
echo.
echo 1. I'll set PostgreSQL password to "postgres" in pgAdmin
echo 2. Update .env with my PostgreSQL password
echo.
set /p choice="Enter choice (1 or 2): "

if "%choice%"=="1" (
    echo.
    echo Please do this in pgAdmin:
    echo 1. Open pgAdmin
    echo 2. Expand "Login/Group Roles"
    echo 3. Right-click "postgres" -^> Properties
    echo 4. Definition tab -^> Set password to: postgres
    echo 5. Click Save
    echo.
    echo Then press any key to restart services...
    pause >nul
    docker-compose restart web
    echo.
    echo Services restarted. Try accessing again.
    pause
    exit /b 0
)

if "%choice%"=="2" (
    echo.
    set /p newpassword="Enter your PostgreSQL password: "
    echo.
    echo Updating .env file...
    powershell -Command "$content = Get-Content .env -Raw; $content = $content -replace 'DATABASE_URL=postgresql://postgres:[^@]*@', \"DATABASE_URL=postgresql://postgres:${newpassword}@\"; $content | Set-Content .env -NoNewline"
    echo.
    echo Restarting services...
    docker-compose restart web
    echo.
    echo Services restarted. Try accessing again.
    pause
    exit /b 0
)

echo Invalid choice.
pause














