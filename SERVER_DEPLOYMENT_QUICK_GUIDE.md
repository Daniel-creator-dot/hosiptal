# 🚀 Server Deployment Quick Guide - All Errors Fixed

## ⚡ Quick Fix (Run on Server)

### Option 1: Automated Fix Script (Recommended)
```bash
cd /var/www/hms  # or your project directory
chmod +x fix_server_deployment.sh
./fix_server_deployment.sh
```

### Option 2: Python Script
```bash
python fix_server_deployment_errors.py
```

### Option 3: Pre-Deployment Check
```bash
python server_deployment_fixes.py
```

---

## 🔧 Common Errors Fixed

### 1. Static Files Not Loading
**Error**: `404 Not Found` for CSS/JS files

**Fix**:
```bash
# Collect static files
python manage.py collectstatic --noinput --clear

# Fix permissions
sudo chown -R www-data:www-data staticfiles
sudo chmod -R 755 staticfiles
```

**Prevention**: ✅ STATIC_ROOT now configurable via `STATIC_ROOT` env var

---

### 2. Media Files Not Uploading
**Error**: `Permission denied` when uploading files

**Fix**:
```bash
# Create media directory
mkdir -p media
sudo chown -R www-data:www-data media
sudo chmod -R 755 media
```

**Prevention**: ✅ MEDIA_ROOT now configurable via `MEDIA_ROOT` env var

---

### 3. Database Connection Timeout
**Error**: `Connection timeout` or `Connection refused`

**Fix**: ✅ Added connection timeout settings (30 seconds)
- Automatically configured in production mode
- Configurable via database OPTIONS

---

### 4. Missing Directories
**Error**: `Directory does not exist`

**Fix**: ✅ Automatic directory creation
- Directories created on startup (WSGI/ASGI)
- Fix scripts create all required directories

---

### 5. File Permission Errors
**Error**: `Permission denied`

**Fix**:
```bash
# Run fix script
./fix_server_deployment.sh

# Or manually
sudo chown -R www-data:www-data /var/www/hms
sudo chmod -R 755 /var/www/hms/staticfiles
sudo chmod -R 755 /var/www/hms/media
```

---

### 6. Path Errors (Windows vs Linux)
**Error**: Path issues on different OS

**Fix**: ✅ Cross-platform path handling
- Uses Path objects
- Handles both string and Path
- Works on Windows, Linux, macOS

---

### 7. Environment Variable Errors
**Error**: Missing environment variables

**Fix**: ✅ Validation and defaults
- Required vars checked
- Clear error messages
- Default values for development

---

## 📋 Server Deployment Checklist

### Before Uploading:
- [ ] Run `python server_deployment_fixes.py` (pre-check)
- [ ] Verify `.env` file has all required variables
- [ ] Test locally first

### After Uploading to Server:

1. **Create Directories**:
   ```bash
   mkdir -p staticfiles media logs
   ```

2. **Set Permissions**:
   ```bash
   sudo chown -R www-data:www-data staticfiles media
   sudo chmod -R 755 staticfiles media
   ```

3. **Run Fix Script**:
   ```bash
   ./fix_server_deployment.sh
   ```

4. **Verify**:
   ```bash
   python manage.py check
   python manage.py check --deploy
   ```

5. **Collect Static Files**:
   ```bash
   python manage.py collectstatic --noinput
   ```

6. **Run Migrations**:
   ```bash
   python manage.py migrate --noinput
   ```

---

## 🔐 Required Environment Variables

### Minimum Required:
```bash
DATABASE_URL=postgresql://user:password@host:port/database
```

### For Production:
```bash
SECRET_KEY=your-very-secure-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

### Optional (Custom Paths):
```bash
STATIC_ROOT=/var/www/hms/staticfiles
MEDIA_ROOT=/var/www/hms/media
```

---

## 🛠️ Troubleshooting

### Static Files Still Not Loading:
1. Check STATIC_ROOT path in settings
2. Verify staticfiles directory exists
3. Check Nginx/Apache configuration
4. Verify file permissions

### Media Files Still Not Uploading:
1. Check MEDIA_ROOT path in settings
2. Verify media directory exists and is writable
3. Check file permissions
4. Check disk space

### Database Connection Issues:
1. Verify DATABASE_URL is correct
2. Check PostgreSQL is running
3. Verify network connectivity
4. Check firewall rules

### Permission Errors:
1. Run fix script: `./fix_server_deployment.sh`
2. Check web server user (usually `www-data`)
3. Verify ownership: `ls -la staticfiles media`
4. Fix: `sudo chown -R www-data:www-data staticfiles media`

---

## ✅ What's Fixed

- ✅ Static files configuration (env var support)
- ✅ Media files configuration (env var support)
- ✅ File permissions (auto-fix scripts)
- ✅ Database connection (timeout settings)
- ✅ Path handling (cross-platform)
- ✅ Directory creation (automatic)
- ✅ Environment validation (checks)
- ✅ WSGI/ASGI startup (directory creation)

---

## 🎯 Result

**All common server deployment errors are now fixed!**

The system automatically:
- Creates required directories
- Handles file permissions
- Configures paths correctly
- Validates environment variables
- Sets up database connections properly

**Your application is ready for server deployment!** 🚀

---

## 📚 Files Created

1. `fix_server_deployment_errors.py` - Python fix script
2. `fix_server_deployment.sh` - Bash fix script
3. `server_deployment_fixes.py` - Pre-deployment checker
4. `QUICK_SERVER_FIX.bat` - Windows quick fix
5. `SERVER_DEPLOYMENT_ERRORS_FIXED.md` - Complete documentation

---

**Run the fix script on your server and all errors will be resolved!** ✅



