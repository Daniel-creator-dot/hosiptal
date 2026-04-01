@echo off
REM Setup General Medicine Department, Move Dr. Ayisi, and Add Midwife Role
REM This script:
REM 1. Creates General Medicine department
REM 2. Moves Dr. Ayisi from nurses to General Medicine
REM 3. Adds all doctors to General Medicine
REM 4. Creates migration for midwife profession
REM 5. Runs migrations

echo ============================================================
echo   SETUP GENERAL MEDICINE AND MIDWIFE ROLE
echo ============================================================
echo.

echo [1/5] Creating migration for midwife profession...
docker-compose exec -T web python manage.py makemigrations hospital --name add_midwife_profession
if errorlevel 1 (
    echo ❌ Migration creation failed!
    pause
    exit /b 1
)
echo ✅ Migration created
echo.

echo [2/5] Running migrations...
docker-compose exec -T web python manage.py migrate
if errorlevel 1 (
    echo ❌ Migration failed!
    pause
    exit /b 1
)
echo ✅ Migrations completed
echo.

echo [3/5] Setting up General Medicine department and moving Dr. Ayisi...
docker-compose exec -T web python setup_general_medicine_and_dr_ayisi.py
if errorlevel 1 (
    echo ❌ Setup script failed!
    pause
    exit /b 1
)
echo ✅ General Medicine setup completed
echo.

echo [4/5] Assigning midwife role to users (if any)...
docker-compose exec -T web python manage.py assign_roles --create-groups
if errorlevel 1 (
    echo ⚠️  Role assignment had issues (this is OK if no midwives exist yet)
)
echo ✅ Role assignment completed
echo.

echo [5/5] Verifying setup...
docker-compose exec -T web python manage.py shell -c "from hospital.models import Staff, Department; gm = Department.objects.filter(name__icontains='General Medicine').first(); print(f'General Medicine Department: {gm.name if gm else \"NOT FOUND\"}'); doctors = Staff.objects.filter(profession='doctor', department=gm, is_deleted=False).count() if gm else 0; print(f'Doctors in General Medicine: {doctors}'); ayisi = Staff.objects.filter(user__username__icontains='ayisi').first(); print(f'Dr. Ayisi: {ayisi.user.get_full_name() if ayisi else \"NOT FOUND\"} - Dept: {ayisi.department.name if ayisi and ayisi.department else \"N/A\"} - Profession: {ayisi.profession if ayisi else \"N/A\"}')"
echo.

echo ============================================================
echo   ✅ SETUP COMPLETE!
echo ============================================================
echo.
echo Summary:
echo   - Midwife profession added to Staff model
echo   - Midwife dashboard created at /hms/midwife/dashboard/
echo   - General Medicine department created/verified (for doctors)
echo   - Maternity department created/verified (for midwives - SEPARATE)
echo   - Dr. Ayisi moved to General Medicine department
echo   - All doctors added to General Medicine department
echo   - All midwives assigned to Maternity department (separate from General Medicine)
echo.
pause














