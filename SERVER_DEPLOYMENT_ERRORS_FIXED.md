# ✅ Server Deployment Errors - All Fixed!

## 🔍 Common Server Deployment Errors Fixed

### 1. **Static Files Errors**
- ✅ **Issue**: Static files not loading (404 errors)
- ✅ **Fix**: 
  - Made STATIC_ROOT configurable via environment variable
  - Added automatic directory creation
  - Fixed path handling for different OS
  - Added proper permissions handling

### 2. **Media Files Errors**
- ✅ **Issue**: Media uploads failing, files not accessible
- ✅ **Fix**:
  - Made MEDIA_ROOT configurable via environment variable
  - Added automatic directory creation
  - Fixed path handling
  - Added proper permissions handling

### 3. **File Permissions Errors**
- ✅ **Issue**: Permission denied errors on static/media files
- ✅ **Fix**:
  - Created fix script for permissions
  - Added automatic permission setting
  - Handles both root and non-root users

### 4. **Database Connection Errors**
- ✅ **Issue**: Database connection timeouts, connection refused
- ✅ **Fix**:
  - Added connection timeout settings
  - Added query timeout settings
  - Improved connection pooling
  - Better error handling

### 5. **Path Errors**
- ✅ **Issue**: Path issues on different OS (Windows vs Linux)
- ✅ **Fix**:
  - Made paths configurable via environment variables
  - Handles both string and Path objects
  - Works on Windows, Linux, and macOS

### 6. **Missing Directories**
- ✅ **Issue**: Directories don't exist, causing errors
- ✅ **Fix**:
  - Automatic directory creation
  - Creates all required subdirectories
  - Handles errors gracefully

### 7. **Environment Variable Errors**
- ✅ **Issue**: Missing or incorrect environment variables
- ✅ **Fix**:
  - Added validation checks
  - Clear error messages
  - Default values for development

---

## 📋 Files Created

### 1. **fix_server_deployment_errors.py**
Python script that:
- Creates required directories
- Fixes file permissions
- Collects static files
- Checks database connection
- Validates settings
- Runs migrations

**Usage:**
```bash
python fix_server_deployment_errors.py
```

### 2. **fix_server_deployment.sh**
Bash script for Linux servers that:
- Creates directories
- Fixes permissions
- Checks .env file
- Tests database connection
- Runs migrations
- Collects static files

**Usage:**
```bash
chmod +x fix_server_deployment.sh
./fix_server_deployment.sh
```

### 3. **server_deployment_fixes.py**
Pre-deployment checker that:
- Checks paths
- Validates environment variables
- Checks file permissions
- Generates deployment checklist

**Usage:**
```bash
python server_deployment_fixes.py
```

---

## 🔧 Settings Updated

### `hms/settings.py` Changes:

1. **STATIC_ROOT** - Now configurable via environment:
   ```python
   STATIC_ROOT = config('STATIC_ROOT', default=str(BASE_DIR / 'staticfiles'))
   ```

2. **MEDIA_ROOT** - Now configurable via environment:
   ```python
   MEDIA_ROOT = config('MEDIA_ROOT', default=str(BASE_DIR / 'media'))
   ```

3. **Database Settings** - Enhanced for production:
   ```python
   # Production database settings
   DATABASES['default']['OPTIONS'] = {
       'connect_timeout': 30,
       'options': '-c statement_timeout=30000',
   }
   ```

---

## 🚀 Quick Server Deployment Steps

### Step 1: Upload Files
```bash
# Upload your project to server
scp -r /path/to/chm user@server:/var/www/hms
```

### Step 2: Run Fix Script
```bash
cd /var/www/hms
chmod +x fix_server_deployment.sh
./fix_server_deployment.sh
```

Or use Python script:
```bash
python fix_server_deployment_errors.py
```

### Step 3: Configure Environment
```bash
# Edit .env file
nano .env

# Set these variables:
DATABASE_URL=postgresql://user:pass@localhost:5432/db
SECRET_KEY=your-secure-secret-key
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

### Step 4: Set Permissions (if needed)
```bash
sudo chown -R www-data:www-data /var/www/hms/staticfiles
sudo chown -R www-data:www-data /var/www/hms/media
sudo chmod -R 755 /var/www/hms/staticfiles
sudo chmod -R 755 /var/www/hms/media
```

### Step 5: Configure Web Server
See `deployment/hms-nginx.conf` for Nginx configuration

### Step 6: Start Services
```bash
# Using Supervisor
sudo supervisorctl start hms

# Or using systemd
sudo systemctl start hms
```

---

## ✅ Common Errors Fixed

| Error | Cause | Fix |
|-------|-------|-----|
| `404 Not Found` for static files | STATIC_ROOT not set correctly | ✅ Configurable via env var |
| `Permission denied` | Wrong file permissions | ✅ Auto-fix script |
| `Directory does not exist` | Missing directories | ✅ Auto-create script |
| `Database connection timeout` | No timeout settings | ✅ Added timeout config |
| `Path errors` | OS-specific path issues | ✅ Cross-platform handling |
| `Environment variable missing` | Not set in .env | ✅ Validation checks |

---

## 🎯 Environment Variables Reference

### Required:
```bash
DATABASE_URL=postgresql://user:password@host:port/database
```

### Recommended for Production:
```bash
SECRET_KEY=your-very-secure-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

### Optional (for custom paths):
```bash
STATIC_ROOT=/var/www/hms/staticfiles
MEDIA_ROOT=/var/www/hms/media
```

---

## 📝 Pre-Deployment Checklist

Run before deploying:
```bash
python server_deployment_fixes.py
```

This will check:
- ✅ Paths are correct
- ✅ Environment variables are set
- ✅ Directories exist
- ✅ Permissions are correct
- ✅ Database connection works

---

## 🔧 Troubleshooting

### Static Files Not Loading:
```bash
# Recollect static files
python manage.py collectstatic --noinput --clear

# Fix permissions
chmod -R 755 staticfiles
chown -R www-data:www-data staticfiles
```

### Media Files Not Uploading:
```bash
# Create media directory
mkdir -p media
chmod -R 755 media
chown -R www-data:www-data media
```

### Database Connection Failed:
```bash
# Check connection
python manage.py dbshell

# Verify DATABASE_URL in .env
cat .env | grep DATABASE_URL
```

### Permission Errors:
```bash
# Run fix script
./fix_server_deployment.sh

# Or manually
sudo chown -R www-data:www-data /var/www/hms
sudo chmod -R 755 /var/www/hms
```

---

## ✅ Summary

All common server deployment errors have been fixed:

- ✅ Static files configuration
- ✅ Media files configuration
- ✅ File permissions handling
- ✅ Database connection robustness
- ✅ Path handling (cross-platform)
- ✅ Directory creation
- ✅ Environment variable validation
- ✅ Automated fix scripts

**Your application is now ready for server deployment!** 🚀

---

## 📚 Additional Resources

- `PRODUCTION_DEPLOYMENT_GUIDE.md` - Complete deployment guide
- `DOCKER_PRODUCTION_SETUP.md` - Docker deployment guide
- `deployment/hms-nginx.conf` - Nginx configuration
- `deployment/deploy.sh` - Deployment script



