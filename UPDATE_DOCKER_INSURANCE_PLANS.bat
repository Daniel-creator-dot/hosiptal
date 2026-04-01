@echo off
REM Update Docker with Insurance Plans changes
REM This ensures all companies have plans and restarts Docker

echo ========================================
echo Updating Docker with Insurance Plans
echo ========================================
echo.

cd /d "%~dp0"

echo [1/5] Ensuring all companies have plans...
docker-compose exec -T web python manage.py ensure_all_companies_have_plans

echo.
echo [2/5] Stopping web service...
docker-compose stop web

echo.
echo [3/5] Rebuilding web container...
docker-compose build web

echo.
echo [4/5] Starting web service...
docker-compose up -d web

echo.
echo [5/5] Waiting for service to be healthy...
timeout /t 10 /nobreak >nul

echo.
echo ========================================
echo Verifying insurance plans...
echo ========================================
docker-compose exec -T web python manage.py shell -c "from hospital.models_insurance_companies import InsuranceCompany, InsurancePlan; print(f'Companies: {InsuranceCompany.objects.filter(is_deleted=False).count()}'); print(f'Plans: {InsurancePlan.objects.filter(is_deleted=False).count()}'); companies_without = [c for c in InsuranceCompany.objects.filter(is_active=True, is_deleted=False) if c.plans.filter(is_deleted=False).count() == 0]; print(f'Companies without plans: {len(companies_without)}')"

echo.
echo ========================================
echo Update Complete!
echo ========================================
echo.
echo All insurance companies now have plans.
echo Docker has been restarted with updates.
echo.
pause
