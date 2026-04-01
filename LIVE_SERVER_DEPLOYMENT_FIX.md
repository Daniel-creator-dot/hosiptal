# 🚀 Live Server Deployment Fix - Complete Guide

## Issues Fixed

### 1. ✅ Email/Username Login Support
**Problem:** Settings required email authentication but login form only supported username.

**Solution:**
- Created custom authentication backend (`hospital/backends.py`) that supports both username AND email
- Updated login form to show appropriate label based on authentication method
- Login view now handles both username and email input

**Files Changed:**
- `hospital/backends.py` (NEW) - Custom authentication backend
- `hospital/templates/hospital/login.html` - Updated form labels
- `hospital/views_auth.py` - Enhanced to support email lookup
- `hms/settings.py` - Added custom backend to AUTHENTICATION_BACKENDS

### 2. ✅ Production Settings (ALLOWED_HOSTS & CSRF)
**Problem:** Production deployments failed due to incorrect ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS.

**Solution:**
- Enhanced ALLOWED_HOSTS configuration with production warnings
- Automatic CSRF_TRUSTED_ORIGINS generation from ALLOWED_HOSTS in production
- Support for both HTTP and HTTPS origins
- Automatic port detection (80, 443, 8000, 8080)

**Files Changed:**
- `hms/settings.py` - Enhanced ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS logic

### 3. ✅ Error Handling
**Status:** Error handlers already exist and are properly configured.

**Files:**
- `hms/views.py` - Custom error handlers (404, 500, 403)
- `hospital/templates/hospital/errors/` - Error page templates

## 📋 Deployment Checklist

### Before Deploying to Live Server

#### 1. Environment Variables (.env file)

Create a `.env` file in your project root with these settings:

```bash
# ====================================
# PRODUCTION SETTINGS
# ====================================

# Security
DEBUG=False
SECRET_KEY=your-super-secret-key-change-this-in-production

# Domain Configuration
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
SITE_URL=https://yourdomain.com

# CSRF Configuration (auto-generated from ALLOWED_HOSTS, but you can override)
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/hms_production
DATABASE_SSL_MODE=prefer
DATABASE_CONN_MAX_AGE=600

# Email Configuration (REQUIRED for email login)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@yourdomain.com

# SMS Configuration (if using SMS features)
SMS_API_KEY=your-sms-api-key
SMS_SENDER_ID=YourHospitalName
```

#### 2. Database Setup

```bash
# Run migrations
python manage.py migrate

# Create superuser (if not exists)
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput
```

#### 3. Verify Settings

```bash
# Check if settings are correct
python manage.py check --deploy
```

#### 4. Test Login

1. **Test Username Login:**
   - Go to `/hms/login/`
   - Enter username and password
   - Should redirect to role-specific dashboard

2. **Test Email Login:**
   - Go to `/hms/login/`
   - Enter email address and password
   - Should work the same as username login

3. **Test Admin Login:**
   - Go to `/admin/`
   - Should work independently from main login

## 🔧 Common Issues & Solutions

### Issue 1: "DisallowedHost" Error
**Error:** `Invalid HTTP_HOST header: 'yourdomain.com'`

**Solution:**
```bash
# Add your domain to ALLOWED_HOSTS in .env
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

### Issue 2: CSRF Token Errors
**Error:** `CSRF verification failed`

**Solution:**
```bash
# Add your domain to CSRF_TRUSTED_ORIGINS in .env
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

**Note:** CSRF_TRUSTED_ORIGINS is now auto-generated from ALLOWED_HOSTS in production, but you can override if needed.

### Issue 3: Email Login Not Working
**Error:** Can't login with email address

**Solution:**
1. Verify user has email set in database:
   ```bash
   python manage.py shell
   >>> from django.contrib.auth import get_user_model
   >>> User = get_user_model()
   >>> user = User.objects.get(username='admin')
   >>> print(user.email)  # Should show email address
   ```

2. Verify authentication backend is configured:
   - Check `hms/settings.py` has `hospital.backends.EmailOrUsernameModelBackend` in AUTHENTICATION_BACKENDS

### Issue 4: Only Admin Login Works
**Error:** Main login page doesn't show or redirects incorrectly

**Solution:**
1. Check URL routing:
   - Main login: `/hms/login/`
   - Admin login: `/admin/`
   - These are separate and should both work

2. Check if user is already logged in:
   - Clear browser cookies
   - Try incognito/private browsing mode

3. Check middleware order in `hms/settings.py`:
   - `AuthenticationMiddleware` should be present
   - `AccountMiddleware` (allauth) should be present

### Issue 5: Error Codes Appearing
**Error:** 500, 404, or 403 errors in production

**Solution:**
1. Check error logs:
   ```bash
   # Django logs
   tail -f logs/django.log
   
   # Server logs (if using gunicorn/nginx)
   tail -f /var/log/nginx/error.log
   ```

2. Enable error email notifications:
   ```python
   # In hms/settings.py (already configured)
   ADMINS = [('Admin', 'admin@yourdomain.com')]
   ```

3. Check error page templates exist:
   - `hospital/templates/hospital/errors/404.html`
   - `hospital/templates/hospital/errors/500.html`
   - `hospital/templates/hospital/errors/403.html`

## 🚀 Production Deployment Steps

### Step 1: Prepare Environment
```bash
# Create .env file with production settings
cp env.example .env
# Edit .env with your production values
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Database Migration
```bash
python manage.py migrate
```

### Step 4: Collect Static Files
```bash
python manage.py collectstatic --noinput
```

### Step 5: Create Superuser
```bash
python manage.py createsuperuser
```

### Step 6: Test Configuration
```bash
python manage.py check --deploy
```

### Step 7: Run Server
```bash
# Development (for testing)
python manage.py runserver 0.0.0.0:8000

# Production (using Gunicorn)
gunicorn hms.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

## 🔒 Security Checklist

- [ ] `DEBUG=False` in production
- [ ] Strong `SECRET_KEY` set
- [ ] `ALLOWED_HOSTS` configured with your domain(s)
- [ ] `CSRF_TRUSTED_ORIGINS` includes your domain(s)
- [ ] HTTPS/SSL enabled (if using HTTPS)
- [ ] Database credentials secure
- [ ] Email credentials secure
- [ ] Static files served correctly
- [ ] Error pages don't expose sensitive information

## 📞 Support

If you encounter issues:

1. Check error logs in `logs/django.log`
2. Verify all environment variables are set correctly
3. Test login with both username and email
4. Verify database connection
5. Check that all migrations are applied

## ✅ Verification

After deployment, verify:

1. ✅ Main login page loads at `/hms/login/`
2. ✅ Admin login page loads at `/admin/`
3. ✅ Can login with username
4. ✅ Can login with email address
5. ✅ Redirects to correct dashboard after login
6. ✅ No error codes in production
7. ✅ Static files load correctly
8. ✅ Email functionality works (if configured)

---

**Last Updated:** $(date)
**Version:** 1.0.0




