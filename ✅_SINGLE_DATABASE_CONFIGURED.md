# ✅ Single PostgreSQL Database Configuration - Complete!

## 🎯 Rule Established

**All services (Docker Desktop, Cursor server, local development) now use the SAME PostgreSQL database URL.**

## 📋 What Was Changed

### **1. Created `.env` File (Single Source of Truth)**
- Centralized database configuration
- All services read from this file
- Single place to change database URL

### **2. Updated `docker-compose.yml`**
- All services now use `env_file: - .env`
- Docker services override hostname to `db` (Docker service name)
- All services use the same database credentials

### **3. Updated `hms/settings.py`**
- Explicitly reads `DATABASE_URL` from `.env`
- Clear documentation about single database rule
- Same database URL for all Django processes

## 🔧 Database Configuration

### **Master Configuration (`.env` file):**
```
DATABASE_URL=postgresql://hms_user:hms_password@localhost:5432/hms_db
```

### **Docker Services (automatic override):**
```
DATABASE_URL=postgresql://hms_user:hms_password@db:5432/hms_db
```
*(Hostname changes from `localhost` to `db` for Docker networking)*

### **Local/Cursor Server:**
```
DATABASE_URL=postgresql://hms_user:hms_password@localhost:5432/hms_db
```
*(Uses `localhost` as defined in `.env`)*

## ✅ Services Using Same Database

All these services connect to **ONE** PostgreSQL database:

1. ✅ **Docker Web Service** (`web`)
   - Reads from `.env` → Overrides hostname to `db`
   - Database: `hms_db`

2. ✅ **Docker Celery Worker** (`celery`)
   - Reads from `.env` → Overrides hostname to `db`
   - Database: `hms_db`

3. ✅ **Docker Celery Beat** (`celery-beat`)
   - Reads from `.env` → Overrides hostname to `db`
   - Database: `hms_db`

4. ✅ **Local Development** (Cursor server, runserver, etc.)
   - Reads from `.env` → Uses `localhost`
   - Database: `hms_db`

5. ✅ **Management Commands** (run from host)
   - Reads from `.env` → Uses `localhost`
   - Database: `hms_db`

## 🔒 Database Details

**Database Name:** `hms_db`  
**User:** `hms_user`  
**Password:** `hms_password`  
**Host (Docker):** `db` (Docker service name)  
**Host (Local):** `localhost`  
**Port:** `5432`

## 📝 How It Works

### **Configuration Flow:**

```
.env file (master config)
    ↓
docker-compose.yml (reads .env, overrides hostname for Docker)
    ↓
Docker services → postgresql://hms_user:hms_password@db:5432/hms_db

.env file (master config)
    ↓
settings.py (reads .env, uses as-is for local)
    ↓
Local/Cursor → postgresql://hms_user:hms_password@localhost:5432/hms_db
```

**Result:** All services connect to the **SAME** PostgreSQL database (`hms_db`)

## 🛠️ Tools Created

### **1. `.env` File**
- Single source of truth for database configuration
- All services reference this file

### **2. `ENFORCE_SINGLE_DATABASE.bat`**
- Verifies all services use same database
- Checks configuration consistency
- Windows batch script for easy verification

### **3. `SINGLE_DATABASE_CONFIG.md`**
- Complete documentation
- Explains how configuration works
- Troubleshooting guide

## ✅ Benefits

1. **Single Source of Truth**
   - One `.env` file controls all database connections
   - No duplicate configuration

2. **Consistency**
   - All services use same database
   - No data synchronization issues

3. **Easy Management**
   - Change database URL in one place (`.env`)
   - All services automatically update

4. **No Conflicts**
   - Docker and local services can run simultaneously
   - Different hostnames (`db` vs `localhost`) but same database

## 🔄 Changing Database URL

**To change database for ALL services:**

1. Edit `.env` file:
   ```
   DATABASE_URL=postgresql://NEW_USER:NEW_PASSWORD@NEW_HOST:5432/NEW_DB
   ```

2. Restart Docker services:
   ```bash
   docker-compose restart
   ```

3. That's it! All services use the new database.

## ✅ Verification

### **Check Docker Services:**
```bash
docker-compose exec web python manage.py shell -c "from django.conf import settings; print(settings.DATABASES['default']['NAME'])"
```

### **Check Local/Cursor:**
```bash
python manage.py shell -c "from django.conf import settings; print(settings.DATABASES['default']['NAME'])"
```

Both should show: `hms_db`

---

**Status:** ✅ **SINGLE DATABASE RULE ENFORCED**

**All services (Docker Desktop, Cursor server, local) now use ONE PostgreSQL database!**

**Date:** November 27, 2025

**Database:** `hms_db` (PostgreSQL)

**Configuration Source:** `.env` file





