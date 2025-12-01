# 🔐 Docker Login Credentials

**Quick reference for logging into your HMS application running in Docker.**

---

## ✅ Default Admin Credentials

**Username:** `admin`  
**Password:** `admin123`

**Access URLs:**
- 🌐 Admin Panel: http://localhost:8000/admin/
- 🏥 HMS Login: http://localhost:8000/hms/login/
- ❤️ Health Check: http://localhost:8000/health/

---

## 🔧 Create/Reset Admin User

### Quick Method (Windows):
```bash
docker-create-admin.bat
```

### Manual Method:
```bash
docker-compose exec web python manage.py createsuperuser
```

### Or use Python shell:
```bash
docker-compose exec web python manage.py shell
```

Then in the shell:
```python
from django.contrib.auth import get_user_model
User = get_user_model()
user, created = User.objects.get_or_create(
    username='admin',
    defaults={'email': 'admin@hospital.com', 'is_staff': True, 'is_superuser': True}
)
user.set_password('admin123')
user.is_staff = True
user.is_superuser = True
user.is_active = True
user.save()
print('✅ Admin user created!' if created else '✅ Admin password reset!')
```

---

## 🔄 Reset All Passwords

### Quick Method (Windows):
```bash
docker-reset-all-passwords.bat
```

This will reset:
- **Admin users**: `admin123`
- **Staff users**: `staff123`

---

## 📋 List All Users

```bash
docker-compose exec web python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); [print(f'{u.username} - is_staff: {u.is_staff}, is_superuser: {u.is_superuser}') for u in User.objects.all()]"
```

---

## 🔑 Reset Specific User Password

```bash
docker-compose exec web python manage.py shell
```

Then:
```python
from django.contrib.auth import get_user_model
User = get_user_model()
user = User.objects.get(username='username_here')
user.set_password('new_password_here')
user.save()
print(f'✅ Password reset for {user.username}')
```

---

## 🆘 Troubleshooting

### Can't Login?

1. **Verify admin user exists:**
   ```bash
   docker-compose exec web python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); admin = User.objects.filter(username='admin').first(); print('Admin exists:', admin is not None)"
   ```

2. **Reset admin password:**
   ```bash
   docker-create-admin.bat
   ```

3. **Check if user is active:**
   ```bash
   docker-compose exec web python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); admin = User.objects.filter(username='admin').first(); print('Is Active:', admin.is_active if admin else 'User not found')"
   ```

4. **Unlock locked accounts:**
   ```bash
   docker-compose exec web python manage.py shell -c "from hospital.models_login_attempts import LoginAttempt; LoginAttempt.objects.filter(is_locked=True).update(is_locked=False); print('✅ Unlocked all accounts')"
   ```

### Account Locked?

The system may lock accounts after failed login attempts. To unlock:

```bash
docker-compose exec web python manage.py shell -c "from hospital.models_login_attempts import LoginAttempt; LoginAttempt.objects.all().update(is_locked=False, failed_attempts=0); print('✅ All accounts unlocked')"
```

---

## ⚠️ Security Notes

1. **Change default passwords immediately** after first login
2. **Use strong passwords** in production
3. **Don't share credentials** publicly
4. **Enable 2FA** if available
5. **Regular password updates** recommended

---

## 📝 Quick Commands Reference

| Task | Command |
|------|---------|
| Create admin | `docker-create-admin.bat` |
| Reset all passwords | `docker-reset-all-passwords.bat` |
| Create superuser (interactive) | `docker-compose exec web python manage.py createsuperuser` |
| List users | `docker-compose exec web python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); [print(u.username) for u in User.objects.all()]"` |
| Unlock accounts | `docker-compose exec web python manage.py shell -c "from hospital.models_login_attempts import LoginAttempt; LoginAttempt.objects.all().update(is_locked=False)"` |

---

**Need help?** Check the logs: `docker-compose logs web`

