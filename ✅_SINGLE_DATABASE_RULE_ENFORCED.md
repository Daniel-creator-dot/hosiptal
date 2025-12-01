# ✅ Single PostgreSQL Database Rule - Enforced!

## 🎯 Rule Established

**All services (Docker Desktop, Cursor server, local development) now use the SAME PostgreSQL database URL.**

## 📋 Configuration Summary

### **Single Source of Truth: `.env` File**

All database configuration is centralized in `.env` file:

```
DATABASE_URL=postgresql://hms_user:hms_password@localhost:5432/hms_db
```

### **How Services Connect:**

1. **Docker Services** (web, celery, celery-beat):
   - Read from `.env` file
   - Override hostname to `db` (Docker service name)
   - Connect to: `postgresql://hms_user:hms_password@db:5432/hms_db`

2. **Local/Cursor Server**:
   - Read from `.env` file
   - Use `localhost` as defined
   - Connect to: `postgresql://hms_user:hms_password@localhost:5432/hms_db`

**Result:** All services connect to the **SAME** database (`hms_db`)

## ✅ Verification Results

**Docker Web Service:**
- Database: `hms_db` ✅
- User: `hms_user` ✅
- Host: `db` ✅
- Port: `5432` ✅

**All services verified to use the same database!**

## 🔧 Files Modified

1. **`docker-compose.yml`**
   - Added `env_file: - .env` to all services
   - All services read from `.env` file
   - Docker services override hostname to `db`

2. **`hms/settings.py`**
   - Explicitly reads `DATABASE_URL` from `.env`
   - Clear documentation about single database rule

3. **`.env.template`**
   - Template file for database configuration
   - Copy to `.env` to use

## 🛠️ Tools Created

1. **`SETUP_SINGLE_DATABASE.bat`**
   - Creates `.env` file if missing
   - Verifies configuration
   - Restarts services

2. **`ENFORCE_SINGLE_DATABASE.bat`**
   - Verifies all services use same database
   - Checks configuration consistency

3. **`CREATE_ENV_FILE.bat`**
   - Creates `.env` file from template

## 📝 Usage

### **Initial Setup:**
```bash
SETUP_SINGLE_DATABASE.bat
```

### **Verify Configuration:**
```bash
ENFORCE_SINGLE_DATABASE.bat
```

### **Change Database URL:**
1. Edit `.env` file
2. Run: `docker-compose restart`

## ✅ Benefits

1. **Single Source of Truth**
   - One `.env` file controls all connections
   - No duplicate configuration

2. **Consistency**
   - All services use same database
   - No data synchronization issues

3. **Easy Management**
   - Change database URL in one place
   - All services automatically update

4. **No Conflicts**
   - Docker and local can run simultaneously
   - Different hostnames but same database

---

**Status:** ✅ **SINGLE DATABASE RULE ENFORCED**

**All services (Docker Desktop, Cursor server, local) use ONE PostgreSQL database!**

**Date:** November 27, 2025

**Database:** `hms_db` (PostgreSQL)

**Configuration Source:** `.env` file





