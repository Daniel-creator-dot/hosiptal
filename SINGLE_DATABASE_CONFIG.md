# ✅ Single PostgreSQL Database Configuration

## 🎯 Rule: All Services Use One Database URL

**All services (Docker Desktop, Cursor server, local development) now use the SAME PostgreSQL database.**

## 📋 Configuration Files

### **1. `.env` File (Single Source of Truth)**
```
DATABASE_URL=postgresql://hms_user:hms_password@localhost:5432/hms_db
```

This is the **master configuration** that all services reference.

### **2. `docker-compose.yml`**
- All services read from `.env` file
- Docker services automatically use `db` hostname instead of `localhost`
- All services use: `postgresql://hms_user:hms_password@db:5432/hms_db`

### **3. `hms/settings.py`**
- Reads `DATABASE_URL` from `.env` file
- Uses the same database URL for all Django processes

## 🔧 How It Works

### **For Docker Services:**
```
.env file → docker-compose.yml → Environment override → Same database
```

1. `.env` defines: `postgresql://hms_user:hms_password@localhost:5432/hms_db`
2. `docker-compose.yml` reads `.env` file
3. Docker services override hostname to `db` (Docker service name)
4. Result: `postgresql://hms_user:hms_password@db:5432/hms_db`

### **For Local/Cursor Server:**
```
.env file → settings.py → Same database
```

1. `.env` defines: `postgresql://hms_user:hms_password@localhost:5432/hms_db`
2. `settings.py` reads from `.env` file
3. Result: `postgresql://hms_user:hms_password@localhost:5432/hms_db`

## ✅ Services Using Same Database

All these services use **ONE** PostgreSQL database:

1. ✅ **Docker Web Service** (`web`)
   - Database: `postgresql://hms_user:hms_password@db:5432/hms_db`

2. ✅ **Docker Celery Worker** (`celery`)
   - Database: `postgresql://hms_user:hms_password@db:5432/hms_db`

3. ✅ **Docker Celery Beat** (`celery-beat`)
   - Database: `postgresql://hms_user:hms_password@db:5432/hms_db`

4. ✅ **Local Development** (Cursor server, runserver, etc.)
   - Database: `postgresql://hms_user:hms_password@localhost:5432/hms_db`

5. ✅ **Management Commands** (run from host)
   - Database: `postgresql://hms_user:hms_password@localhost:5432/hms_db`

## 🔒 Database Connection Details

**Database Name:** `hms_db`  
**User:** `hms_user`  
**Password:** `hms_password`  
**Host (Docker):** `db` (Docker service name)  
**Host (Local):** `localhost`  
**Port:** `5432`

## 📝 Important Notes

1. **Single Source of Truth**: `.env` file is the only place to change database URL
2. **Automatic Override**: Docker services automatically use `db` hostname
3. **Same Database**: All services connect to the same PostgreSQL instance
4. **No Conflicts**: Docker and local services can run simultaneously (different hostnames)

## 🛠️ Changing Database URL

**To change the database URL for ALL services:**

1. Edit `.env` file:
   ```
   DATABASE_URL=postgresql://NEW_USER:NEW_PASSWORD@NEW_HOST:5432/NEW_DB
   ```

2. Restart services:
   ```bash
   docker-compose restart
   ```

3. That's it! All services will use the new database.

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

**Status:** ✅ **SINGLE DATABASE CONFIGURATION ACTIVE**

**All services now use one PostgreSQL database!**





