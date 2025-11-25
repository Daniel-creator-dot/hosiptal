# Login Troubleshooting Guide

## Quick Fix Commands

### On Your VPS:

```bash
cd /var/www/chm
git pull origin main
source venv/bin/activate
chmod +x fix_login_complete.sh fix_login_issues.py reset_user_password.py
bash fix_login_complete.sh
```

## Step-by-Step Diagnosis

### 1. Run Login Diagnostic

```bash
cd /var/www/chm
source venv/bin/activate
python fix_login_issues.py
```

This will show:
- Database connection status
- If auth tables exist
- If users exist
- User account status
- Settings configuration

### 2. Check Database Connection

```bash
python check_database.py
```

### 3. Check if Users Exist

```bash
python manage.py shell
```

In Python shell:
```python
from django.contrib.auth.models import User
print(f"Total users: {User.objects.count()}")
for u in User.objects.all():
    print(f"  - {u.username} (Active: {u.is_active}, Staff: {u.is_staff})")
```

### 4. Create Superuser (if no users)

```bash
python manage.py createsuperuser
```

Or use the script:
```bash
python reset_user_password.py --create
```

### 5. Reset Password (if user exists but can't login)

```bash
# Method 1: Django command
python manage.py changepassword <username>

# Method 2: Script
python reset_user_password.py <username> <new_password>

# Method 3: Python shell
python manage.py shell
```

In shell:
```python
from django.contrib.auth.models import User
u = User.objects.get(username='your_username')
u.set_password('new_password')
u.is_active = True
u.save()
print("Password reset!")
```

### 6. Check Gunicorn Logs

```bash
sudo journalctl -u gunicorn-chm.service -f
```

Look for:
- Database connection errors
- Authentication errors
- Session errors
- CSRF errors

### 7. Check Session Configuration

```bash
python manage.py shell
```

```python
from django.conf import settings
print(f"SESSION_ENGINE: {settings.SESSION_ENGINE}")
print(f"SESSION_COOKIE_SECURE: {settings.SESSION_COOKIE_SECURE}")
print(f"CSRF_COOKIE_SECURE: {settings.CSRF_COOKIE_SECURE}")
```

## Common Issues

### Issue 1: "No users found"

**Fix:**
```bash
python manage.py createsuperuser
```

### Issue 2: "Invalid username or password"

**Possible causes:**
1. Wrong password
2. User is inactive
3. Password hash is corrupted

**Fix:**
```bash
# Reset password
python reset_user_password.py <username> <new_password>

# Or activate user
python manage.py shell
```
```python
from django.contrib.auth.models import User
u = User.objects.get(username='username')
u.is_active = True
u.save()
```

### Issue 3: "Database connection failed"

**Fix:**
```bash
# Check PostgreSQL
sudo systemctl status postgresql
sudo systemctl start postgresql

# Check .env file
cat .env | grep DATABASE_URL

# Test connection
python check_database.py
```

### Issue 4: "CSRF verification failed"

**Fix:**
Check your `.env` file:
```env
DEBUG=False
CSRF_COOKIE_SECURE=True
SESSION_COOKIE_SECURE=True
```

Or if using HTTP (not HTTPS):
```env
DEBUG=True
CSRF_COOKIE_SECURE=False
SESSION_COOKIE_SECURE=False
```

### Issue 5: "Session expired" or "Please login again"

**Fix:**
```bash
# Clear session data
python manage.py shell
```
```python
from django.contrib.sessions.models import Session
Session.objects.all().delete()
print("Sessions cleared")
```

### Issue 6: Login page shows but form doesn't submit

**Check:**
1. CSRF token is present in form
2. JavaScript is working
3. No console errors in browser

**Fix:**
```bash
# Collect static files
python manage.py collectstatic --noinput

# Restart Gunicorn
sudo systemctl restart gunicorn-chm.service
```

## Complete Reset (Last Resort)

If nothing works:

```bash
cd /var/www/chm
source venv/bin/activate

# 1. Reset database (WARNING: Deletes all data!)
sudo -u postgres psql <<EOF
DROP DATABASE IF EXISTS hms_db;
CREATE DATABASE hms_db;
GRANT ALL PRIVILEGES ON DATABASE hms_db TO hms_user;
\q
EOF

# 2. Run migrations
python manage.py migrate

# 3. Create superuser
python manage.py createsuperuser

# 4. Collect static
python manage.py collectstatic --noinput

# 5. Restart service
sudo systemctl restart gunicorn-chm.service
```

## Testing Login

After fixes:

1. **Test from browser:**
   - Visit: `http://your-vps-ip/hms/login/`
   - Enter username and password
   - Should redirect to dashboard

2. **Test from command line:**
   ```bash
   python manage.py shell
   ```
   ```python
   from django.contrib.auth import authenticate
   user = authenticate(username='your_username', password='your_password')
   if user:
       print(f"✅ Login successful: {user.username}")
   else:
       print("❌ Login failed")
   ```

3. **Check logs:**
   ```bash
   sudo journalctl -u gunicorn-chm.service -f
   ```

## Quick Reference

```bash
# Diagnostic
python fix_login_issues.py

# Reset password
python reset_user_password.py <username> <new_password>

# Create user
python manage.py createsuperuser

# Check database
python check_database.py

# Check logs
sudo journalctl -u gunicorn-chm.service -f

# Restart service
sudo systemctl restart gunicorn-chm.service
```







