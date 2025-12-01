# 🔐 Docker Login - FIXED!

**Your login credentials are now set up and ready to use!**

---

## ✅ Default Admin Credentials

**Username:** `admin`  
**Password:** `admin123`

---

## 🌐 Access Your Application

- **Admin Panel**: http://localhost:8000/admin/
- **HMS Login**: http://localhost:8000/hms/login/
- **Health Check**: http://localhost:8000/health/

---

## 🔧 Quick Fix Scripts

### If you need to fix login issues again:

**Windows:**
```bash
docker-fix-login.bat
```

This script will:
- ✅ Create/reset admin user
- ✅ Unlock all locked accounts
- ✅ Activate all users
- ✅ Set default password to `admin123`

### Create custom admin user:
```bash
docker-create-admin.bat
```

### Reset all passwords:
```bash
docker-reset-all-passwords.bat
```

---

## 📋 Manual Commands

### Create superuser (interactive):
```bash
docker-compose exec web python manage.py createsuperuser
```

### Reset admin password:
```bash
docker-compose exec web python manage.py shell
```

Then in Python shell:
```python
from django.contrib.auth import get_user_model
User = get_user_model()
user = User.objects.get(username='admin')
user.set_password('admin123')
user.is_staff = True
user.is_superuser = True
user.is_active = True
user.save()
print('✅ Password reset!')
```

### Unlock locked accounts:
```bash
docker-compose exec web python manage.py shell -c "from hospital.models_login_attempts import LoginAttempt; LoginAttempt.objects.all().update(is_locked=False, failed_attempts=0); print('✅ All accounts unlocked')"
```

---

## 🆘 Troubleshooting

### Still can't login?

1. **Run the fix script:**
   ```bash
   docker-fix-login.bat
   ```

2. **Check if admin exists:**
   ```bash
   docker-compose exec web python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); admin = User.objects.filter(username='admin').first(); print('Admin exists:', admin is not None)"
   ```

3. **Check container logs:**
   ```bash
   docker-compose logs web
   ```

4. **Restart containers:**
   ```bash
   docker-compose restart web
   ```

---

## ⚠️ Security Reminder

**Change the default password after first login!**

The default password `admin123` is for initial setup only. Please change it to a strong password in production.

---

## ✅ Status

- ✅ Admin user created: `admin`
- ✅ Password set: `admin123`
- ✅ User is active
- ✅ User is superuser
- ✅ User is staff

**You're all set! Try logging in now at http://localhost:8000/admin/**

