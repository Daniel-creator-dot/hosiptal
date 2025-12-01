@echo off
echo ========================================
echo LIST ALL USERS
echo ========================================
echo.

docker-compose exec web python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); all_users = User.objects.all().order_by('username'); print(f'Total users: {all_users.count()}'); print(); print('Username                 | Full Name              | Staff | Active | Superuser'); print('-' * 75); [print(f'{u.username:24} | {u.get_full_name():22} | {str(u.is_staff):5} | {str(u.is_active):6} | {str(u.is_superuser):9}') for u in all_users]"

echo.
pause














