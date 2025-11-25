# 📁 Where is My Database?

## Quick Answer

It depends on which database you're using:

### Currently You Have:
✅ **SQLite** → `C:\Users\user\chm\db.sqlite3` (23.7 MB)

### When You Deploy with MySQL:
✅ **MySQL** → No file! It's on the MySQL server (managed by cPanel/MySQL service)

### If You Use PostgreSQL:
✅ **PostgreSQL** → No file! It's on the PostgreSQL server

## Database Locations by Type

### 1. SQLite (Your Current Database)
**Location:** `C:\Users\user\chm\db.sqlite3`

```
chm/
├── db.sqlite3          ← YOUR DATABASE IS HERE (23.7 MB)
├── manage.py
├── hms/
├── hospital/
└── ...
```

**Details:**
- ✅ Single file: `db.sqlite3`
- ✅ Size: 23.7 MB (as of now)
- ✅ Location: Project root folder
- ✅ Easy to backup: Just copy this file
- ✅ Easy to restore: Replace with backup file

**To Backup SQLite:**
```bash
# Copy the file
copy db.sqlite3 db_backup_20241112.sqlite3

# Or use Django command
python manage.py dumpdata > data_backup.json
```

### 2. MySQL (For Your Managed Server)
**Location:** No file! MySQL stores data in its own data directory

**MySQL Data Location (you don't need to access this):**
- Linux: `/var/lib/mysql/`
- Windows: `C:\ProgramData\MySQL\MySQL Server X.X\Data\`
- cPanel: Managed by hosting provider

**How to Access:**
- ✅ Via cPanel → MySQL Databases → phpMyAdmin
- ✅ Via command: `mysql -u username -p database_name`
- ✅ Via Django: `python manage.py dbshell`

**To Backup MySQL:**
```bash
# Via command line
mysqldump -u username -p database_name > backup.sql

# Via cPanel
# Go to phpMyAdmin → Export → Go

# Via Django
python manage.py dumpdata > data_backup.json
```

### 3. PostgreSQL (If You Use It)
**Location:** No file! PostgreSQL stores data in its own data directory

**PostgreSQL Data Location (you don't need to access this):**
- Linux: `/var/lib/postgresql/data/`
- Windows: `C:\Program Files\PostgreSQL\X.X\data\`

**How to Access:**
- ✅ Via command: `psql -U username -d database_name`
- ✅ Via Django: `python manage.py dbshell`
- ✅ Via pgAdmin (GUI tool)

**To Backup PostgreSQL:**
```bash
# Via command line
pg_dump -U username database_name > backup.sql

# Via Django
python manage.py dumpdata > data_backup.json
```

## Current Database File Details

```
📁 Your Current Database:
   Location: C:\Users\user\chm\db.sqlite3
   Size: 23,736,320 bytes (23.7 MB)
   Type: SQLite3
   Last Modified: November 12, 2025, 5:38 PM
```

## What's Inside Your Database?

Your `db.sqlite3` contains:
- ✅ **Patients** (35,067+ patients)
- ✅ **Staff** records
- ✅ **Appointments**
- ✅ **Encounters** (patient visits)
- ✅ **Billing** records
- ✅ **Lab** orders and results
- ✅ **Pharmacy** inventory
- ✅ **Accounting** data
- ✅ **All other HMS data**

## Important Files Related to Database

```
C:\Users\user\chm\
├── db.sqlite3                    ← Current database (23.7 MB)
├── manage.py                     ← Django management script
├── hms/
│   └── settings.py              ← Database configuration
├── hospital/
│   └── migrations/              ← Database schema changes
└── backups/                     ← Backup files (if any)
```

## How to Check Database Location

### Method 1: Check Settings
```python
# Look in hms/settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',  ← Database location
    }
}
```

### Method 2: Django Shell
```bash
python manage.py shell

# Then:
from django.conf import settings
print(settings.DATABASES['default']['NAME'])
```

### Method 3: Django Command
```bash
python manage.py dbshell
# This opens your database directly
```

## When You Switch to MySQL

After you configure MySQL, your data will move from:
- ❌ `db.sqlite3` file
- ✅ MySQL server (managed by cPanel)

**To migrate from SQLite to MySQL:**
```bash
# 1. Export current data
python manage.py dumpdata > data_backup.json

# 2. Change DATABASE_URL in .env to MySQL
DATABASE_URL=mysql://user:pass@localhost:3306/hms_db

# 3. Create new MySQL database structure
python manage.py migrate

# 4. Import your data
python manage.py loaddata data_backup.json
```

## Backup Locations

### Automatic Backups (if configured)
```
C:\Users\user\chm\backups\
├── backup_20241112_120000.json
├── backup_20241112_180000.json
└── db_backup_20241112.sqlite3
```

### Manual Backups
```bash
# Create backup folder
mkdir backups

# Backup database
python manage.py dumpdata > backups/backup_$(date +%Y%m%d).json

# Or copy SQLite file
copy db.sqlite3 backups\db_backup_20241112.sqlite3
```

## Database Size Management

### Check Database Size
```bash
# Windows
Get-Item db.sqlite3 | Select-Object Name, Length

# Result: 23,736,320 bytes (23.7 MB)
```

### Monitor Growth
```python
# In Django shell
from hospital.models import *

print(f"Patients: {Patient.objects.count()}")
print(f"Encounters: {Encounter.objects.count()}")
print(f"Appointments: {Appointment.objects.count()}")
```

## Important: Database Differences

### SQLite (Current)
```
Location: Single file (db.sqlite3)
Backup: Copy the file
Restore: Replace the file
Access: Direct file access
Size: ~24 MB currently
```

### MySQL (Production)
```
Location: MySQL server
Backup: mysqldump or cPanel
Restore: mysql import or cPanel
Access: Via MySQL client/phpMyAdmin
Size: Managed by MySQL server
```

### PostgreSQL (Alternative)
```
Location: PostgreSQL server
Backup: pg_dump
Restore: pg_restore
Access: Via psql/pgAdmin
Size: Managed by PostgreSQL server
```

## Quick Reference

| Database | File Location | Size | Backup Method |
|----------|--------------|------|---------------|
| **SQLite** | `C:\Users\user\chm\db.sqlite3` | 23.7 MB | Copy file |
| **MySQL** | MySQL Server | N/A | mysqldump |
| **PostgreSQL** | PG Server | N/A | pg_dump |

## Common Questions

### Q: Can I delete db.sqlite3?
**A:** No! That's your entire database. Always backup first.

### Q: Can I move db.sqlite3?
**A:** Yes, but update `settings.py` to point to new location.

### Q: Will I lose data when switching to MySQL?
**A:** No, if you export first:
```bash
python manage.py dumpdata > backup.json
```

### Q: Where is MySQL database stored?
**A:** On MySQL server. You access via phpMyAdmin/command line, not as a file.

### Q: How to backup before switching?
```bash
# Option 1: Django dump (recommended)
python manage.py dumpdata > full_backup.json

# Option 2: Copy SQLite file
copy db.sqlite3 db_backup_SAFE.sqlite3
```

### Q: Can I have both SQLite and MySQL?
**A:** Yes! Keep SQLite as backup while testing MySQL:
```python
# In settings.py, you can configure multiple databases
DATABASES = {
    'default': {...},  # MySQL
    'sqlite_backup': {...}  # SQLite
}
```

## Recommended Actions Before Production

### 1. Backup Current Database
```bash
# Create backups folder
mkdir backups

# Full Django backup (recommended)
python manage.py dumpdata --natural-foreign --natural-primary > backups/full_backup_20241112.json

# Copy SQLite file (additional safety)
copy db.sqlite3 backups\db.sqlite3.backup

# Test restore
# python manage.py loaddata backups/full_backup_20241112.json
```

### 2. Document Database Info
```bash
# Check what's in database
python manage.py showmigrations
python manage.py dbshell
```

### 3. Prepare for MySQL Migration
See: `MYSQL_QUICK_START.md`

## Summary

### Your Current Database:
```
📁 File: C:\Users\user\chm\db.sqlite3
📊 Size: 23.7 MB
🗃️ Type: SQLite3
💾 Contains: All your HMS data
📅 Last Modified: Nov 12, 2025, 5:38 PM
```

### When You Deploy to Production with MySQL:
```
📁 File: None (server-based)
📊 Size: Managed by MySQL
🗃️ Type: MySQL
💾 Contains: Will contain all your HMS data
🌐 Access: Via cPanel/phpMyAdmin
```

### Backup Strategy:
```
✅ Keep db.sqlite3 as backup
✅ Export with: python manage.py dumpdata
✅ Can restore to any database type
✅ Safe migration to MySQL anytime
```

---

**Current Status:** Using SQLite (file-based)
**File Location:** `C:\Users\user\chm\db.sqlite3`
**Next Step:** When ready, migrate to MySQL for production
**Safe:** Keep SQLite backup after migration!















