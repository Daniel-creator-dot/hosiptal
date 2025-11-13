# 🚀 Remote PostgreSQL Database Setup Guide
## Separate Database Server for Maximum Performance

This guide explains how to configure your HMS to use a PostgreSQL database hosted on a separate server, which significantly improves performance, scalability, and reliability.

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Benefits of Remote Database](#benefits)
3. [Prerequisites](#prerequisites)
4. [Step-by-Step Setup](#setup)
5. [Security Configuration](#security)
6. [Performance Optimization](#performance)
7. [Monitoring & Maintenance](#monitoring)
8. [Troubleshooting](#troubleshooting)

---

## 🏗️ Architecture Overview

```
┌─────────────────────────┐         ┌─────────────────────────┐
│   Application Server    │         │   Database Server       │
│   (HMS Django App)      │◄───────►│   (PostgreSQL)          │
│   IP: 192.168.1.10      │  5432   │   IP: 192.168.1.20      │
│   Port: 8000            │         │   Port: 5432            │
└─────────────────────────┘         └─────────────────────────┘
         ▲                                      ▲
         │                                      │
         └──────── Secure Connection ──────────┘
              (SSL/TLS Encrypted)
```

### Why This Architecture?

**Application Server:**
- Handles HTTP requests
- Runs Django application
- Processes business logic
- Serves static files

**Database Server:**
- Dedicated to database operations
- Optimized for data storage/retrieval
- Better resource allocation
- Easier to scale

---

## ✅ Benefits of Remote Database

### Performance Benefits
- ✅ **Dedicated Resources** - Database gets its own CPU, RAM, and disk I/O
- ✅ **Better Scaling** - Scale database and application independently
- ✅ **Reduced Latency** - Optimized network between servers
- ✅ **Faster Queries** - Database server tuned specifically for PostgreSQL

### Reliability Benefits
- ✅ **High Availability** - Database failures don't affect app server
- ✅ **Better Backups** - Dedicated backup server/process
- ✅ **Easy Maintenance** - Update app without touching database
- ✅ **Disaster Recovery** - Separate physical/cloud locations

### Cost Benefits
- ✅ **Right-Sizing** - Pay for exactly what you need
- ✅ **Cloud Options** - Use managed PostgreSQL services
- ✅ **Reduced Downtime** - Maintenance without full shutdown

---

## 📋 Prerequisites

### On Database Server (PostgreSQL Server)

1. **PostgreSQL Installed** (Version 14+ recommended)
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install postgresql postgresql-contrib
   
   # CentOS/RHEL
   sudo yum install postgresql-server postgresql-contrib
   
   # Or use managed services:
   # - Amazon RDS for PostgreSQL
   # - Google Cloud SQL for PostgreSQL
   # - Azure Database for PostgreSQL
   # - DigitalOcean Managed Databases
   # - Heroku Postgres
   ```

2. **Firewall Configuration**
   - Port 5432 open for PostgreSQL
   - IP whitelist for application server

3. **System Requirements**
   - **Minimum:** 2 CPU, 4GB RAM, 50GB SSD
   - **Recommended:** 4 CPU, 8GB RAM, 100GB SSD
   - **Production:** 8+ CPU, 16GB+ RAM, 250GB+ SSD

### On Application Server (HMS Server)

1. **Python 3.11+ installed**
2. **PostgreSQL client libraries**
   ```bash
   # Ubuntu/Debian
   sudo apt install libpq-dev
   
   # CentOS/RHEL
   sudo yum install postgresql-devel
   ```

3. **Python PostgreSQL driver**
   ```bash
   pip install psycopg2-binary
   # Or for production:
   pip install psycopg2
   ```

---

## 🔧 Step-by-Step Setup

### Step 1: Configure PostgreSQL Server

#### 1.1 Create Database and User

SSH into your database server:

```bash
# Switch to postgres user
sudo -u postgres psql

# In PostgreSQL shell:
CREATE DATABASE hms_production;
CREATE USER hms_user WITH PASSWORD 'your_strong_password_here';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE hms_production TO hms_user;

-- Grant schema privileges
\c hms_production
GRANT ALL ON SCHEMA public TO hms_user;

-- Exit
\q
```

#### 1.2 Configure PostgreSQL for Remote Connections

Edit PostgreSQL configuration:

```bash
# Find your config file location
sudo find /etc -name postgresql.conf

# Edit postgresql.conf
sudo nano /etc/postgresql/14/main/postgresql.conf
```

**Important Settings:**

```conf
# Network Settings
listen_addresses = '*'          # Listen on all interfaces
port = 5432

# Connection Settings
max_connections = 200           # Adjust based on your needs
superuser_reserved_connections = 3

# Memory Settings (adjust based on your server RAM)
shared_buffers = 2GB           # 25% of RAM
effective_cache_size = 6GB     # 75% of RAM
work_mem = 16MB
maintenance_work_mem = 512MB

# Query Planner
random_page_cost = 1.1         # For SSD storage
effective_io_concurrency = 200 # For SSD storage

# Write Ahead Log (WAL)
wal_buffers = 16MB
min_wal_size = 1GB
max_wal_size = 4GB

# Checkpoint
checkpoint_completion_target = 0.9

# Logging (important for monitoring)
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d.log'
log_statement = 'mod'          # Log data-modifying statements
log_duration = on
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
```

#### 1.3 Configure Client Authentication

Edit pg_hba.conf:

```bash
sudo nano /etc/postgresql/14/main/pg_hba.conf
```

Add your application server IP:

```conf
# TYPE  DATABASE        USER            ADDRESS                 METHOD

# Local connections
local   all             postgres                                peer
local   all             all                                     peer

# IPv4 local connections
host    all             all             127.0.0.1/32            scram-sha-256

# Allow HMS application server (replace with your app server IP)
host    hms_production  hms_user        192.168.1.10/32         scram-sha-256

# For multiple app servers, add multiple lines:
# host    hms_production  hms_user        192.168.1.11/32         scram-sha-256
# host    hms_production  hms_user        192.168.1.12/32         scram-sha-256

# SSL connections (more secure)
hostssl hms_production  hms_user        0.0.0.0/0               scram-sha-256
```

**Security Note:** Replace `192.168.1.10` with your actual application server IP!

#### 1.4 Restart PostgreSQL

```bash
sudo systemctl restart postgresql
sudo systemctl status postgresql
```

#### 1.5 Test Remote Connection

From your application server:

```bash
# Test connection
psql -h 192.168.1.20 -U hms_user -d hms_production

# If successful, you'll see:
# hms_production=>
```

---

### Step 2: Configure Firewall

#### On Database Server:

**UFW (Ubuntu/Debian):**
```bash
# Allow PostgreSQL from app server
sudo ufw allow from 192.168.1.10 to any port 5432

# Check status
sudo ufw status
```

**Firewalld (CentOS/RHEL):**
```bash
# Allow PostgreSQL
sudo firewall-cmd --permanent --add-port=5432/tcp
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="192.168.1.10" port protocol="tcp" port="5432" accept'
sudo firewall-cmd --reload
```

**Cloud Providers:**
- **AWS:** Configure Security Group to allow port 5432 from app server
- **Google Cloud:** Configure Firewall Rules
- **Azure:** Configure Network Security Group
- **DigitalOcean:** Configure Cloud Firewalls

---

### Step 3: Configure HMS Application

#### 3.1 Update .env File

On your application server, edit `.env`:

```bash
# Remote PostgreSQL Configuration
DATABASE_URL=postgresql://hms_user:your_strong_password_here@192.168.1.20:5432/hms_production

# Enable SSL for production (recommended)
DATABASE_SSL_MODE=require

# Connection Pool Settings
DATABASE_CONN_MAX_AGE=600
DATABASE_CONN_HEALTH_CHECKS=True

# Database Performance
DATABASE_MAX_CONNECTIONS=100
DATABASE_TIMEOUT=10
```

**Real-World Examples:**

**Private Network:**
```bash
DATABASE_URL=postgresql://hms_user:SecurePass123!@192.168.1.20:5432/hms_production
```

**Cloud Managed Database:**
```bash
# AWS RDS
DATABASE_URL=postgresql://hms_user:SecurePass123!@hms-db.c9akl7xvbqmf.us-east-1.rds.amazonaws.com:5432/hms_production

# DigitalOcean
DATABASE_URL=postgresql://hms_user:SecurePass123!@hms-db-do-user-123456-0.b.db.ondigitalocean.com:25060/hms_production?sslmode=require

# Heroku
DATABASE_URL=postgresql://user:pass@ec2-52-21-252-142.compute-1.amazonaws.com:5432/d8fjk3lk4j5l
```

#### 3.2 Install Python Dependencies

```bash
# On application server
pip install psycopg2-binary
pip install dj-database-url

# Or add to requirements.txt:
echo "psycopg2-binary==2.9.9" >> requirements.txt
pip install -r requirements.txt
```

#### 3.3 Test Connection

```bash
# Test Django database connection
python manage.py check --database default

# Should show: System check identified no issues (0 silenced).
```

#### 3.4 Run Migrations

```bash
# Create database tables on remote server
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

---

## 🔒 Security Configuration

### Enable SSL/TLS Encryption

#### On Database Server:

1. **Generate SSL Certificates:**

```bash
# Create certificates directory
sudo mkdir -p /etc/postgresql/14/main/ssl
cd /etc/postgresql/14/main/ssl

# Generate self-signed certificate (for testing)
sudo openssl req -new -x509 -days 365 -nodes -text \
  -out server.crt \
  -keyout server.key \
  -subj "/CN=hms-db.example.com"

# Set permissions
sudo chmod 600 server.key
sudo chown postgres:postgres server.key server.crt
```

2. **Enable SSL in postgresql.conf:**

```conf
ssl = on
ssl_cert_file = '/etc/postgresql/14/main/ssl/server.crt'
ssl_key_file = '/etc/postgresql/14/main/ssl/server.key'
```

3. **Restart PostgreSQL:**

```bash
sudo systemctl restart postgresql
```

#### On Application Server:

Update your `.env`:

```bash
DATABASE_URL=postgresql://hms_user:password@192.168.1.20:5432/hms_production?sslmode=require
```

**SSL Modes:**
- `disable` - No SSL (not recommended)
- `allow` - Try SSL, fall back to non-SSL
- `prefer` - Try SSL first (default)
- `require` - Force SSL, don't verify certificate
- `verify-ca` - Force SSL, verify CA
- `verify-full` - Force SSL, verify CA and hostname

---

## ⚡ Performance Optimization

### 1. Connection Pooling

Update `hms/settings.py`:

```python
# Already configured! But you can adjust:
DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL'),
        conn_max_age=600,  # Keep connections for 10 minutes
        conn_health_checks=True,  # Check before using
    )
}

# For high-traffic sites, use PgBouncer
# DATABASE_URL=postgresql://hms_user:pass@localhost:6432/hms_production
# (PgBouncer listens on 6432, proxies to PostgreSQL on 5432)
```

### 2. Install PgBouncer (Optional, for high traffic)

**On Database Server:**

```bash
# Install
sudo apt install pgbouncer

# Configure
sudo nano /etc/pgbouncer/pgbouncer.ini
```

**PgBouncer Configuration:**

```ini
[databases]
hms_production = host=localhost port=5432 dbname=hms_production

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = scram-sha-256
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
reserve_pool_size = 5
```

### 3. Database Query Optimization

```bash
# On application server, enable query logging
DEBUG=False  # In production
DATABASE_QUERY_LOGGING=True  # For monitoring

# Check slow queries on database server
sudo -u postgres psql hms_production
```

```sql
-- Enable slow query logging
ALTER DATABASE hms_production SET log_min_duration_statement = 1000;  -- 1 second

-- Find slow queries
SELECT query, calls, total_time, mean_time 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;
```

### 4. Redis Caching

Reduce database load with Redis:

```bash
# .env file
REDIS_URL=redis://localhost:6379/0
USE_REDIS_CACHE=True
```

---

## 📊 Monitoring & Maintenance

### Database Monitoring

**Install pg_stat_statements:**

```sql
-- On database server
sudo -u postgres psql hms_production

CREATE EXTENSION pg_stat_statements;
```

**Check Database Size:**

```sql
SELECT 
    pg_database.datname,
    pg_size_pretty(pg_database_size(pg_database.datname)) AS size
FROM pg_database
WHERE datname = 'hms_production';
```

**Check Active Connections:**

```sql
SELECT count(*) FROM pg_stat_activity 
WHERE datname = 'hms_production';
```

**Monitor Performance:**

```sql
-- Top queries by time
SELECT 
    substring(query, 1, 50) AS query,
    calls,
    total_time,
    mean_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
```

### Automated Backups

```bash
# Create backup script
sudo nano /usr/local/bin/backup-hms-db.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/var/backups/postgresql"
DATE=$(date +%Y%m%d_%H%M%S)
FILENAME="hms_production_$DATE.sql.gz"

# Create backup
pg_dump -U postgres hms_production | gzip > $BACKUP_DIR/$FILENAME

# Keep only last 30 days
find $BACKUP_DIR -name "hms_production_*.sql.gz" -mtime +30 -delete

echo "Backup completed: $FILENAME"
```

```bash
# Make executable
sudo chmod +x /usr/local/bin/backup-hms-db.sh

# Add to crontab (daily at 2 AM)
sudo crontab -e
0 2 * * * /usr/local/bin/backup-hms-db.sh
```

---

## 🔍 Troubleshooting

### Connection Issues

**Problem:** Can't connect to database

```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Check if port is open
sudo netstat -tulpn | grep 5432

# Test from app server
telnet 192.168.1.20 5432
# OR
nc -zv 192.168.1.20 5432

# Check PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-14-main.log
```

**Problem:** Authentication failed

```bash
# Check pg_hba.conf
sudo cat /etc/postgresql/14/main/pg_hba.conf | grep hms

# Test connection with psql
psql -h 192.168.1.20 -U hms_user -d hms_production -W
```

**Problem:** Too many connections

```sql
-- Check current connections
SELECT count(*) FROM pg_stat_activity;

-- Check max connections
SHOW max_connections;

-- Kill idle connections
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'hms_production'
  AND state = 'idle'
  AND state_change < now() - interval '1 hour';
```

### Performance Issues

**Problem:** Slow queries

```sql
-- Find slow queries
SELECT pid, now() - query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active'
  AND now() - query_start > interval '5 seconds';

-- Analyze table statistics
ANALYZE VERBOSE;

-- Vacuum database
VACUUM ANALYZE;
```

**Problem:** High CPU usage

```bash
# Check active queries
sudo -u postgres psql hms_production -c "
  SELECT pid, query, state
  FROM pg_stat_activity
  WHERE state = 'active';
"

# Check for missing indexes
sudo -u postgres psql hms_production -c "
  SELECT schemaname, tablename, attname, n_distinct, correlation
  FROM pg_stats
  WHERE schemaname = 'public'
  ORDER BY n_distinct DESC;
"
```

---

## 📈 Production Checklist

Before going live with remote PostgreSQL:

- [ ] Database server properly configured
- [ ] Firewall rules set up correctly
- [ ] SSL/TLS encryption enabled
- [ ] Connection tested from app server
- [ ] Migrations run successfully
- [ ] Superuser created
- [ ] Automated backups configured
- [ ] Monitoring enabled
- [ ] Connection pooling configured
- [ ] Performance testing completed
- [ ] Disaster recovery plan documented
- [ ] Team trained on new architecture

---

## 🌐 Cloud Provider Quick Setup

### AWS RDS PostgreSQL

```bash
# 1. Create RDS instance in AWS Console
# 2. Get endpoint URL
# 3. Configure .env

DATABASE_URL=postgresql://hms_user:password@hms-db.c9akl7.us-east-1.rds.amazonaws.com:5432/hms_production?sslmode=require
```

### DigitalOcean Managed Database

```bash
# 1. Create Managed Database
# 2. Add app server to trusted sources
# 3. Get connection details

DATABASE_URL=postgresql://doadmin:password@hms-db-do-user-123456-0.b.db.ondigitalocean.com:25060/hms_production?sslmode=require
```

### Google Cloud SQL

```bash
# 1. Create Cloud SQL instance
# 2. Add authorized network
# 3. Get connection string

DATABASE_URL=postgresql://hms_user:password@34.123.45.67:5432/hms_production
```

---

## 📚 Additional Resources

- [PostgreSQL Official Documentation](https://www.postgresql.org/docs/)
- [Django Database Optimization](https://docs.djangoproject.com/en/stable/topics/db/optimization/)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [PgBouncer Documentation](https://www.pgbouncer.org/usage.html)

---

## 🆘 Support

If you encounter issues:

1. Check PostgreSQL logs: `/var/log/postgresql/`
2. Check Django logs: Check your application logs
3. Test connection: Use `psql` command
4. Review firewall rules
5. Verify credentials in `.env` file

---

## ✅ Summary

You now have:

- ✅ Separate database and application servers
- ✅ Improved performance and scalability
- ✅ Secure SSL connections
- ✅ Connection pooling enabled
- ✅ Automated backups
- ✅ Performance monitoring

Your HMS is now running on a production-grade architecture! 🎉

