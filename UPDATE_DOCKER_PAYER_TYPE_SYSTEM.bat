@echo off
REM Update Docker with Payer Type System changes
REM This restarts the web service to pick up new code changes

echo ========================================
echo Updating Docker with Payer Type System
echo ========================================
echo.

cd /d "%~dp0"

echo [1/4] Stopping web service...
docker-compose stop web

echo.
echo [2/4] Rebuilding web container (to ensure new files are included)...
docker-compose build web

echo.
echo [3/4] Starting web service...
docker-compose up -d web

echo.
echo [4/4] Waiting for service to be healthy...
timeout /t 10 /nobreak >nul

echo.
echo ========================================
echo Checking service status...
echo ========================================
docker-compose ps web

echo.
echo ========================================
echo Verifying new files are in container...
echo ========================================
docker-compose exec -T web ls -la /app/hospital/services/visit_payer_sync_service.py
docker-compose exec -T web ls -la /app/hospital/views_frontdesk_visit.py
docker-compose exec -T web ls -la /app/hospital/signals_visit_payer_sync.py

echo.
echo ========================================
echo Checking if signal is loaded...
echo ========================================
docker-compose exec -T web python manage.py shell -c "import hospital.signals_visit_payer_sync; print('Signal module loaded successfully')" 2>&1 || echo "Signal check failed - may need full restart"

echo.
echo ========================================
echo Update Complete!
echo ========================================
echo.
echo The payer type system should now be active.
echo Restart Docker Desktop if changes don't appear.
echo.
pause
