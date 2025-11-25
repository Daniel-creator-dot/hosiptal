# 🚀 MySQL Quick Start - For Managed Servers

## Your System Already Supports MySQL! ✅

**Good news:** Your HMS is already configured to work with MySQL. No code changes needed!

## 5-Minute Setup for MySQL

### Step 1: Install MySQL Driver (1 minute)
```bash
pip install mysqlclient
```

**If installation fails**, use PyMySQL instead:
```bash
pip install pymysql

# Then add to hms/__init__.py:
import pymysql
pymysql.install_as_MySQLdb()
```

### Step 2: Create MySQL Database (2 minutes)

**Option A: Using cPanel** (Easiest)
1. Login to cPanel
2. Go to **MySQL Databases**
3. Create database: `yourusername_hms`
4. Create user: `yourusername_hmsuser`
5. Set password (save it!)
6. Assign user to database with ALL PRIVILEGES
7. Note the hostname (usually `localhost`)

**Option B: Using Command Line**
```bash
mysql -u root -p

CREATE DATABASE hms_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'hms_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON hms_db.* TO 'hms_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### Step 3: Configure .env File (1 minute)

Create or edit `.env`:
```bash
# MySQL Configuration
DATABASE_URL=mysql://hms_user:your_password@localhost:3306/hms_db

# Django Settings
DEBUG=False
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

**Format:** `mysql://USERNAME:PASSWORD@HOST:PORT/DATABASE_NAME`

### Step 4: Run Migrations (1 minute)
```bash
# Test connection
python manage.py check

# Create tables
python manage.py migrate

# Create admin user
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput
```

### Step 5: Start Server
```bash
# Development
python manage.py runserver

# Production
gunicorn hms.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

## Done! 🎉

Your HMS is now running on MySQL!

## Common DATABASE_URL Examples

### cPanel/Plesk
```bash
DATABASE_URL=mysql://cpanel_user:password@localhost:3306/cpanel_dbname
```

### Remote MySQL
```bash
DATABASE_URL=mysql://user:password@mysql.yourdomain.com:3306/database
```

### Local Development
```bash
DATABASE_URL=mysql://root:password@localhost:3306/hms_local
```

## What if mysqlclient Won't Install?

### Ubuntu/Debian
```bash
sudo apt-get install python3-dev default-libmysqlclient-dev build-essential
pip install mysqlclient
```

### CentOS/RHEL
```bash
sudo yum install python3-devel mysql-devel
pip install mysqlclient
```

### Windows
Download wheel from: https://www.lfd.uci.edu/~gohlke/pythonlibs/#mysqlclient
```bash
pip install mysqlclient‑X.X.X‑cpXX‑cpXX‑win_amd64.whl
```

### Still Having Issues?
Use PyMySQL (pure Python, always works):
```bash
pip install pymysql
```

Then create `hms/__init__.py` if it doesn't exist:
```python
import pymysql
pymysql.install_as_MySQLdb()
```

## Why MySQL is Perfect for Your Managed Server

✅ **Already Installed** - Comes with cPanel/Plesk
✅ **phpMyAdmin** - Web interface for management
✅ **Automatic Backups** - Your host backs it up
✅ **No Extra Cost** - Included in hosting
✅ **Easy to Use** - Familiar to most admins
✅ **Great Performance** - Works perfectly with Django

## MySQL Already Optimized!

Your `settings.py` includes these MySQL optimizations:
- Connection pooling (600s)
- UTF8MB4 character set (full Unicode including emojis)
- Query timeouts (30s)
- Transaction support
- Automatic reconnection

## Verify Everything Works

```bash
# Test database connection
python manage.py dbshell

# Check migrations
python manage.py showmigrations

# Test a query
python manage.py shell
>>> from hospital.models import Patient
>>> Patient.objects.count()
0
```

## Need More Details?

See `DATABASE_SETUP_MYSQL.md` for:
- Troubleshooting guide
- Performance tuning
- Backup strategies
- Migration from PostgreSQL
- Advanced configuration

## Quick Troubleshooting

**Problem:** "No module named 'MySQLdb'"
```bash
pip install mysqlclient
```

**Problem:** "Access denied for user"
- Check username/password in DATABASE_URL
- Verify user has database privileges

**Problem:** "Can't connect to MySQL server"
- Check MySQL is running
- Verify host and port in DATABASE_URL
- Check if remote access is enabled

**Problem:** Installation errors
```bash
# Try PyMySQL instead
pip install pymysql
# Add to hms/__init__.py: import pymysql; pymysql.install_as_MySQLdb()
```

## Summary

1. ✅ Install: `pip install mysqlclient`
2. ✅ Create MySQL database (via cPanel or command line)
3. ✅ Set DATABASE_URL in .env
4. ✅ Run: `python manage.py migrate`
5. ✅ Create admin: `python manage.py createsuperuser`
6. ✅ Done!

**Your system already supports MySQL - just configure it!** 🚀

---

**Next Steps:**
- See `DEPLOYMENT.md` for full production deployment
- See `DATABASE_SETUP_MYSQL.md` for detailed MySQL guide
- See `PRODUCTION_READY.md` for complete system overview
















