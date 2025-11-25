# MySQL Database Setup Guide

## Your System is Ready for MySQL! ✅

Your HMS now supports **both MySQL and PostgreSQL**. Since your managed server uses MySQL, follow this guide.

## Quick Answer
**YES, you should use MySQL** on your managed server. Your system is already configured to work with MySQL perfectly!

## Why Use MySQL on Managed Servers?

✅ **Already installed** - Most managed hosting (cPanel, Plesk) comes with MySQL
✅ **Web interface** - phpMyAdmin for easy management
✅ **Automatic backups** - Hosting providers usually backup MySQL automatically
✅ **No extra setup** - Works out of the box
✅ **Performance** - Django works great with MySQL

## Step 1: Install MySQL Python Driver

```bash
# Activate your virtual environment first
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install MySQL client
pip install mysqlclient
```

### Alternative (if mysqlclient fails):
```bash
pip install pymysql
```

If using PyMySQL, add this to `hms/__init__.py`:
```python
import pymysql
pymysql.install_as_MySQLdb()
```

## Step 2: Create MySQL Database

### Option A: Using cPanel/Plesk (Easiest)
1. Log into your hosting control panel
2. Go to **MySQL Databases**
3. Create new database: `yourusername_hms`
4. Create new user: `yourusername_hmsuser`
5. Set a strong password
6. Grant **ALL PRIVILEGES** to the user on the database
7. Note down: database name, username, password, and host

### Option B: Using MySQL Command Line
```bash
# Log into MySQL
mysql -u root -p

# Create database
CREATE DATABASE hms_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

# Create user
CREATE USER 'hms_user'@'localhost' IDENTIFIED BY 'your_secure_password';

# Grant privileges
GRANT ALL PRIVILEGES ON hms_db.* TO 'hms_user'@'localhost';

# Flush privileges
FLUSH PRIVILEGES;

# Exit
EXIT;
```

### Option C: Using phpMyAdmin
1. Access phpMyAdmin from your hosting panel
2. Click **Databases** tab
3. Enter database name: `hms_db`
4. Choose collation: `utf8mb4_unicode_ci`
5. Click **Create**
6. Go to **Privileges** → **Add user account**
7. Fill in username and password
8. Select "Grant all privileges on database"
9. Click **Go**

## Step 3: Configure DATABASE_URL

Edit your `.env` file:

```bash
# For MySQL
DATABASE_URL=mysql://hms_user:your_password@localhost:3306/hms_db

# Example with cPanel (often uses different host)
DATABASE_URL=mysql://username:password@mysql.yourdomain.com:3306/database_name
```

### DATABASE_URL Format:
```
mysql://USERNAME:PASSWORD@HOST:PORT/DATABASE_NAME
```

**Important Notes:**
- Replace `USERNAME` with your MySQL username
- Replace `PASSWORD` with your MySQL password
- Replace `HOST` with `localhost` or your MySQL server hostname
- PORT is usually `3306` for MySQL
- Replace `DATABASE_NAME` with your database name

## Step 4: Update Requirements

Add MySQL support to `requirements.txt`:

```bash
# Add to requirements.txt
mysqlclient==2.2.0

# Or if using PyMySQL
# pymysql==1.1.0
```

## Step 5: Run Migrations

```bash
# Test database connection
python manage.py check

# Create tables
python manage.py migrate

# Create admin user
python manage.py createsuperuser
```

## MySQL-Specific Settings (Already Configured!)

Your `settings.py` already includes these MySQL optimizations:

```python
# MySQL Performance Optimizations (for managed servers)
if db_engine == 'django.db.backends.mysql':
    DATABASES['default']['OPTIONS'].update({
        'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        'charset': 'utf8mb4',  # Full Unicode support (emojis, etc.)
        'connect_timeout': 10,
        'read_timeout': 30,
        'write_timeout': 30,
        'isolation_level': 'read committed',
    })
    DATABASES['default']['ATOMIC_REQUESTS'] = True
    DATABASES['default']['CONN_MAX_AGE'] = 600  # Connection pooling
```

## Common MySQL Issues & Solutions

### Issue 1: "No module named 'MySQLdb'"
**Solution:**
```bash
pip install mysqlclient
# or
pip install pymysql
```

### Issue 2: mysqlclient installation fails
**Error:** "mysql_config not found"

**Solution (Ubuntu/Debian):**
```bash
sudo apt-get install python3-dev default-libmysqlclient-dev build-essential
pip install mysqlclient
```

**Solution (CentOS/RHEL):**
```bash
sudo yum install python3-devel mysql-devel
pip install mysqlclient
```

**Solution (macOS):**
```bash
brew install mysql
pip install mysqlclient
```

**Solution (Windows):**
- Download mysqlclient wheel from: https://www.lfd.uci.edu/~gohlke/pythonlibs/#mysqlclient
- Install: `pip install mysqlclient‑X.X.X‑cpXX‑cpXX‑win_amd64.whl`

### Issue 3: "Access denied for user"
**Solution:** Check your credentials in DATABASE_URL

### Issue 4: "Can't connect to MySQL server"
**Solution:** 
- Verify MySQL is running
- Check host and port in DATABASE_URL
- Check firewall settings
- For remote MySQL, ensure remote access is enabled

### Issue 5: Character encoding errors
**Solution:** Already handled! Your database uses `utf8mb4`

## MySQL vs PostgreSQL Comparison

| Feature | MySQL | PostgreSQL |
|---------|-------|------------|
| **Availability** | ✅ Pre-installed on most hosts | ❌ Often not available |
| **Control Panel** | ✅ phpMyAdmin included | ❌ No web interface |
| **Backups** | ✅ Automatic by host | ⚠️ Manual setup |
| **Performance** | ✅ Excellent for HMS | ✅ Excellent for HMS |
| **Django Support** | ✅ Full support | ✅ Full support |
| **Setup Complexity** | ✅ Easy | ⚠️ More complex |
| **Cost** | ✅ Included | ⚠️ May cost extra |

## Recommendation for Your Server

### Use MySQL if:
- ✅ Your hosting provides MySQL (cPanel, Plesk, shared hosting)
- ✅ You want easy management via phpMyAdmin
- ✅ You want automatic backups by your host
- ✅ You want minimal setup

### Use PostgreSQL if:
- ⚠️ You have VPS/Dedicated server
- ⚠️ You can install PostgreSQL yourself
- ⚠️ You need advanced database features
- ⚠️ You prefer PostgreSQL specifically

## Production Checklist for MySQL

- [ ] MySQL database created
- [ ] MySQL user created with strong password
- [ ] User has ALL PRIVILEGES on database
- [ ] `mysqlclient` installed: `pip install mysqlclient`
- [ ] DATABASE_URL configured in .env
- [ ] Connection tested: `python manage.py check`
- [ ] Migrations run: `python manage.py migrate`
- [ ] Superuser created: `python manage.py createsuperuser`
- [ ] Static files collected: `python manage.py collectstatic`
- [ ] Database backups configured

## Testing Your MySQL Connection

Create a test file `test_mysql.py`:

```python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import connection

try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT VERSION();")
        version = cursor.fetchone()
        print(f"✅ MySQL Connection Successful!")
        print(f"MySQL Version: {version[0]}")
        
        cursor.execute("SELECT DATABASE();")
        database = cursor.fetchone()
        print(f"Connected to database: {database[0]}")
        
        # Test write
        cursor.execute("SHOW TABLES;")
        tables = cursor.fetchall()
        print(f"Number of tables: {len(tables)}")
        
except Exception as e:
    print(f"❌ Connection Failed: {e}")
```

Run it:
```bash
python test_mysql.py
```

## MySQL Optimization Tips

### 1. Connection Pooling (Already Enabled)
```python
CONN_MAX_AGE = 600  # Keep connections for 10 minutes
```

### 2. Query Optimization
```python
# Use select_related for foreign keys
patients = Patient.objects.select_related('gender')

# Use prefetch_related for many-to-many
encounters = Encounter.objects.prefetch_related('diagnoses')
```

### 3. Database Indexes
```bash
# Check for missing indexes
python manage.py check --database default
```

### 4. Regular Maintenance
```sql
-- Optimize all tables
OPTIMIZE TABLE hospital_patient, hospital_encounter, hospital_appointment;

-- Analyze tables
ANALYZE TABLE hospital_patient;
```

## Backup & Restore

### Manual Backup
```bash
# Backup
mysqldump -u hms_user -p hms_db > backup_$(date +%Y%m%d).sql

# Restore
mysql -u hms_user -p hms_db < backup_20241112.sql
```

### Automated Backup (Cron Job)
```bash
# Add to crontab (crontab -e)
0 2 * * * mysqldump -u hms_user -pYOUR_PASSWORD hms_db > /backup/hms_$(date +\%Y\%m\%d).sql
```

## Migration from PostgreSQL to MySQL (If Needed)

If you already have data in PostgreSQL and want to move to MySQL:

```bash
# 1. Dump data from PostgreSQL
python manage.py dumpdata --natural-foreign --natural-primary > data_backup.json

# 2. Change DATABASE_URL to MySQL

# 3. Run migrations on MySQL
python manage.py migrate

# 4. Load data
python manage.py loaddata data_backup.json
```

## Your System Already Supports Both!

The beauty of Django is that **you don't need to change any code**. Your HMS works with:
- ✅ MySQL
- ✅ PostgreSQL  
- ✅ SQLite (development only)

Just change the `DATABASE_URL` in your `.env` file!

## Quick Start for MySQL

```bash
# 1. Install MySQL driver
pip install mysqlclient

# 2. Create database (via cPanel or MySQL)

# 3. Update .env
echo "DATABASE_URL=mysql://user:password@localhost:3306/hms_db" > .env

# 4. Run migrations
python manage.py migrate

# 5. Create admin
python manage.py createsuperuser

# 6. Start server
python manage.py runserver
```

## Need Help?

### Check Database Connection
```bash
python manage.py dbshell
```

### Check Database Settings
```bash
python manage.py diffsettings | grep DATABASE
```

### Debug Connection Issues
```python
# In Django shell
python manage.py shell

from django.db import connection
print(connection.settings_dict)
```

## Summary

✅ **Your HMS is already MySQL-ready!**
✅ **No code changes needed**
✅ **Just configure DATABASE_URL**
✅ **Install mysqlclient**
✅ **Run migrations**
✅ **You're done!**

**Recommendation:** Use MySQL on your managed server. It's the easiest and most reliable option for cPanel/Plesk hosting.

---

**Pro Tip:** Most hosting providers give you the database details in your control panel. Look for "MySQL Databases" or similar section.
















