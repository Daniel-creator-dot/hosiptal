@echo off
setlocal
cd /d "%~dp0"

if not exist ".env.sync" (
  echo.
  echo ERROR: .env.sync not found.
  echo Copy env.sync.example to .env.sync and set LIVE_DATABASE_URL to your Supabase URL.
  echo.
  pause
  exit /b 1
)

echo [%date% %time%] Starting local -^> live sync...
python auto_sync_local_to_live.py --once
set ERR=%ERRORLEVEL%
if %ERR% NEQ 0 (
  echo Sync failed with exit code %ERR%. See logs\local_to_live_sync.log
) else (
  echo Sync completed. See logs\local_to_live_sync.log
)
exit /b %ERR%
