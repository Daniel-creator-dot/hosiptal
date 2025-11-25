@echo off
echo ========================================
echo UNLOCK ALL BLOCKED ACCOUNTS
echo ========================================
echo.
echo This will unlock ALL blocked accounts:
echo   - Activate all inactive users
echo   - Unlock all login attempts
echo   - Reset failed attempt counters
echo.

docker-compose exec web python unlock_all_accounts.py

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo ✅ ALL ACCOUNTS UNLOCKED!
    echo ========================================
    echo.
) else (
    echo.
    echo ❌ Failed to unlock accounts
    echo.
)

pause






