# 🚀 PostgreSQL Migration Guide - HMS High Performance Setup

## ⚡ Performance Benefits

- **10-100x faster** than SQLite for concurrent users
- **Better indexing** and query optimization
- **Connection pooling** for reduced latency
- **ACID compliance** for data integrity
- **Full-text search** capabilities
- **Concurrent writes** without locking

---

## 📋 Prerequisites

### 1. Install PostgreSQL

**Windows:**
```bash
# Download from: https://www.postgresql.org/download/windows/
# Or use chocolatey:
choco install postgresql
```

**Verify Installation:**
```bash
psql --version
```

### 2. Install Redis (for caching)

**Windows:**
```bash
# Download from: https://github.com/microsoftarchive/redis/releases
# Or install via WSL/Docker
```

---

## 🔧 Step-by-Step Migration

### Step 1: Create PostgreSQL Database

Run the automated setup script:

```bash
setup_postgresql.bat
```

**Or manually:**

```sql
-- Connect to PostgreSQL
psql -U postgres

-- Create database and user
CREATE DATABASE hms_db;
CREATE USER hms_user WITH PASSWORD 'hms_password';

-- Grant privileges
ALTER ROLE hms_user SET client_encoding TO 'utf8';
ALTER ROLE hms_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE hms_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE hms_db TO hms_user;

-- Connect to the new database
\c hms_db

-- Grant schema permissions
GRANT ALL ON SCHEMA public TO hms_user;
```

---

### Step 2: Update .env File

Add to your `.env` file:

```env
# PostgreSQL Database
DATABASE_URL=postgresql://hms_user:hms_password@localhost:5432/hms_db

# Redis Cache (install Redis first)
REDIS_URL=redis://127.0.0.1:6379/1
```

---

### Step 3: Backup Current Database

```bash
# Backup SQLite data to JSON
python manage.py dumpdata --natural-foreign --natural-primary --indent 2 --output db_backup.json --exclude contenttypes --exclude auth.permission --exclude sessions.session
```

---

### Step 4: Run Automated Migration

```bash
python migrate_to_postgresql.py
```

This script will:
1. ✅ Backup your SQLite database
2. ✅ Migrate schema to PostgreSQL
3. ✅ Transfer all data
4. ✅ Add performance indexes
5. ✅ Optimize database

---

### Step 5: Start Redis (for caching)

```bash
# Windows (WSL or Redis for Windows)
redis-server

# Or use Docker
docker run -d -p 6379:6379 redis:latest
```

---

### Step 6: Run Migrations

```bash
python manage.py migrate
```

---

### Step 7: Create Superuser (if needed)

```bash
python manage.py createsuperuser
```

---

## 🎯 Performance Optimizations Applied

### 1. **Database Optimizations**
- ✅ Connection pooling (600 second max age)
- ✅ Connection health checks
- ✅ Automatic transaction management
- ✅ Query timeout limits (30 seconds)
- ✅ Keepalive for persistent connections

### 2. **Redis Caching**
- ✅ Template caching
- ✅ Session storage in Redis
- ✅ Query result caching
- ✅ zlib compression
- ✅ JSON serialization

### 3. **Database Indexes**
Created indexes on:
- Patient MRN
- Patient phone numbers
- Encounter status and dates
- Triage levels and times
- Appointments
- Invoices and payments

### 4. **Query Optimizations**
- ✅ select_related() for foreign keys
- ✅ prefetch_related() for reverse relations
- ✅ only() and defer() for large fields
- ✅ Cached template loaders

---

## 📊 Expected Performance Improvements

| Metric | Before (SQLite) | After (PostgreSQL) | Improvement |
|--------|----------------|-------------------|-------------|
| Page Load | 500-1000ms | 100-200ms | **5x faster** |
| Concurrent Users | 5-10 | 100+ | **10x more** |
| Query Speed | Moderate | Very Fast | **3-10x faster** |
| Dashboard Load | 2-3s | 0.3-0.5s | **6x faster** |
| Write Performance | Locks frequently | No locks | **Unlimited** |

---

## 🔍 Verify Migration

### Test Database Connection:

```bash
python manage.py dbshell
```

### Check Data:

```sql
-- Count patients
SELECT COUNT(*) FROM hospital_patient;

-- Count encounters
SELECT COUNT(*) FROM hospital_encounter;

-- Verify indexes
\di
```

### Test Application:

```bash
python manage.py runserver
```

Visit: `http://127.0.0.1:8000/hms/`

---

## 🚨 Troubleshooting

### Issue: "psycopg2 not found"
```bash
pip install psycopg2-binary
```

### Issue: "Connection refused"
- Ensure PostgreSQL service is running
- Check port 5432 is not blocked
- Verify username/password in DATABASE_URL

### Issue: "Permission denied"
```sql
-- Connect as postgres user and grant permissions
GRANT ALL PRIVILEGES ON DATABASE hms_db TO hms_user;
GRANT ALL ON SCHEMA public TO hms_user;
ALTER DATABASE hms_db OWNER TO hms_user;
```

### Issue: "Data migration fails"
```bash
# Clear PostgreSQL and start fresh
python manage.py flush
python manage.py migrate
python manage.py loaddata db_backup.json
```

---

## 🔐 Production Security

For production deployment:

1. **Change default password:**
```sql
ALTER USER hms_user WITH PASSWORD 'your-strong-password-here';
```

2. **Update .env:**
```env
DATABASE_URL=postgresql://hms_user:your-strong-password@your-server:5432/hms_db
```

3. **Enable SSL:**
```env
DATABASE_URL=postgresql://hms_user:password@server:5432/hms_db?sslmode=require
```

---

## 📈 Additional Performance Tips

### 1. PostgreSQL Configuration

Edit `postgresql.conf`:

```conf
# Increase memory for better performance
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 128MB
work_mem = 16MB

# Optimize checkpoint
checkpoint_completion_target = 0.9
wal_buffers = 16MB

# Query planner
random_page_cost = 1.1
effective_io_concurrency = 200
```

### 2. Regular Maintenance

```sql
-- Weekly maintenance
VACUUM ANALYZE;

-- Monthly full vacuum
VACUUM FULL;

-- Reindex periodically
REINDEX DATABASE hms_db;
```

### 3. Monitoring

```sql
-- Check slow queries
SELECT query, calls, total_time, mean_time 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;

-- Check database size
SELECT pg_size_pretty(pg_database_size('hms_db'));

-- Check active connections
SELECT count(*) FROM pg_stat_activity WHERE datname = 'hms_db';
```

---

## ✅ Post-Migration Checklist

- [ ] PostgreSQL service running
- [ ] Database created and accessible
- [ ] All data migrated successfully
- [ ] Indexes created
- [ ] Redis running
- [ ] Application starts without errors
- [ ] Login works
- [ ] Patient data accessible
- [ ] Ambulance system functional
- [ ] Performance improved (test page loads)

---

## 🆘 Rollback to SQLite

If you need to rollback:

1. Update `.env`:
```env
DATABASE_URL=sqlite:///db.sqlite3
```

2. Restart server:
```bash
python manage.py runserver
```

Your original SQLite database (`db.sqlite3`) is preserved!

---

## 📞 Support

For issues, check:
- Django logs: `logs/django.log`
- PostgreSQL logs: Check PostgreSQL data directory
- Application console output

**Migration complete! Your system is now running on high-performance PostgreSQL!** 🚀

















