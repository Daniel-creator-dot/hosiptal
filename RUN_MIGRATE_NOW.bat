@echo off
REM Run migrations. Use this after pulling code so 1100_walkinpharmacysaleitem_waiver (and others) apply.
REM If web is already running on server: docker compose exec web python manage.py migrate --noinput
echo Running database migrations...
docker-compose run --rm web python manage.py migrate --noinput
if %errorlevel% equ 0 (
    echo Migrations applied successfully.
) else (
    echo Migration failed. Check output above.
    exit /b 1
)
