@echo off
REM Script to update Robbert to superuser in Docker environment (Windows)

echo ==========================================
echo Making Robbert a Superuser in Docker
echo ==========================================
echo.

REM Option 1: Using Django management command
echo Method 1: Using Django management command...
docker-compose exec web python manage.py make_robbert_superuser

REM Option 2: Using Django shell directly
echo.
echo Method 2: Using Django shell...
docker-compose exec web python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); user = None; [user := User.objects.get(username=u) for u in ['robbert.kwamegbologah', 'robbert', 'robbert.kwame'] if User.objects.filter(username=u).exists()]; user = user or User.objects.filter(username__icontains='robbert').first(); user.is_superuser = True if user else None; user.is_staff = True if user else None; user.is_active = True if user else None; user.save() if user else None; print(f'✅ Updated {user.username} to superuser') if user else print('❌ User not found'); print(f'   is_superuser: {user.is_superuser}') if user else None; print(f'   is_staff: {user.is_staff}') if user else None; print(f'   is_active: {user.is_active}') if user else None"

echo.
echo ==========================================
echo Update Complete!
echo ==========================================
echo.
echo IMPORTANT: Robbert must log out and log back in for changes to take effect!
echo.

pause






