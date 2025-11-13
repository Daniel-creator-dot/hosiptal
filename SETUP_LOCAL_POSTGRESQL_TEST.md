# 🧪 Testing Remote Database Setup on Local Machine

## Quick Test: PostgreSQL on Same Machine

This guide helps you test the remote database setup by installing PostgreSQL on your local machine and connecting to it as if it were a remote server.

---

## 📋 Step-by-Step Setup

### Step 1: Install PostgreSQL on Windows

#### Option A: Using Official Installer (Recommended)

1. **Download PostgreSQL:**
   - Go to: https://www.postgresql.org/download/windows/
   - Download PostgreSQL 15 or 16 (latest stable)
   - Or direct link: https://www.enterprisedb.com/downloads/postgres-postgresql-downloads

2. **Run the Installer:**
   - Double-click the downloaded .exe file
   - Click "Next" through the wizard
   - **Important settings:**
     - Install directory: `C:\Program Files\PostgreSQL\16\`
     - Port: `5432` (default)
     - Locale: Default
   - **Set a password** for the postgres superuser
     - Remember this password! (e.g., `admin123`)

3. **Complete Installation:**
   - Install all components (PostgreSQL Server, pgAdmin, Command Line Tools)
   - Click "Finish"

#### Option B: Using Chocolatey (If you have Chocolatey)

```powershell
# Run as Administrator
choco install postgresql
```

---

### Step 2: Verify PostgreSQL is Running

```powershell
# Check if PostgreSQL service is running
Get-Service -Name postgresql*

# You should see:
# Status   Name               DisplayName
# ------   ----               -----------
# Running  postgresql-x64-16  postgresql-x64-16 - PostgreSQL Serv...
```

If it's not running:

```powershell
# Start PostgreSQL service
Start-Service postgresql-x64-16
```

---

### Step 3: Create HMS Database

#### Using Command Line (psql)

1. **Open Command Prompt or PowerShell:**

```powershell
# Navigate to PostgreSQL bin directory
cd "C:\Program Files\PostgreSQL\16\bin"

# Connect to PostgreSQL (enter the password you set during installation)
.\psql.exe -U postgres
```

2. **Create Database and User:**

```sql
-- Create database
CREATE DATABASE hms_test;

-- Create user
CREATE USER hms_user WITH PASSWORD 'hms_password_123';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE hms_test TO hms_user;

-- Connect to the new database
\c hms_test

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO hms_user;

-- Grant default privileges
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO hms_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO hms_user;

-- Exit
\q
```

#### Using pgAdmin (GUI Method)

1. **Open pgAdmin:**
   - Start Menu → PostgreSQL 16 → pgAdmin 4

2. **Connect to PostgreSQL:**
   - Expand "Servers" → "PostgreSQL 16"
   - Enter the password you set during installation

3. **Create Database:**
   - Right-click "Databases" → "Create" → "Database"
   - Name: `hms_test`
   - Owner: `postgres`
   - Click "Save"

4. **Create User:**
   - Right-click "Login/Group Roles" → "Create" → "Login/Group Role"
   - General tab: Name = `hms_user`
   - Definition tab: Password = `hms_password_123`
   - Privileges tab: Check "Can login?"
   - Click "Save"

5. **Grant Privileges:**
   - Right-click `hms_test` database → "Query Tool"
   - Run:
     ```sql
     GRANT ALL ON SCHEMA public TO hms_user;
     ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO hms_user;
     ```

---

### Step 4: Configure HMS to Use PostgreSQL

#### Update .env File

Create or edit `.env` in your HMS project root:

```bash
# PostgreSQL on Local Machine (testing remote setup)
DATABASE_URL=postgresql://hms_user:hms_password_123@localhost:5432/hms_test

# Or use 127.0.0.1 to simulate network connection
# DATABASE_URL=postgresql://hms_user:hms_password_123@127.0.0.1:5432/hms_test

# Optional: Enable SSL (PostgreSQL on Windows may not have SSL by default)
DATABASE_SSL_MODE=prefer

# Connection settings
DATABASE_CONN_MAX_AGE=600
DATABASE_CONN_HEALTH_CHECKS=True
DATABASE_TIMEOUT=10
```

---

### Step 5: Install Python PostgreSQL Driver

```powershell
# In your project directory
pip install psycopg2-binary
```

If you get an error, try:

```powershell
# Alternative: Pure Python implementation
pip install psycopg2-binary --no-binary psycopg2-binary
```

Or:

```powershell
# Precompiled binary for Windows
pip install psycopg2
```

---

### Step 6: Test the Connection

```powershell
# Run the connection test script
python test_db_connection.py
```

**Expected Output:**

```
======================================================================
TESTING DATABASE CONNECTION
======================================================================

Database Configuration:
----------------------------------------------------------------------
  Engine: django.db.backends.postgresql
  Name: hms_test
  Host: localhost
  Port: 5432
  User: hms_user
  Connection Max Age: 600 seconds

Testing connection...
----------------------------------------------------------------------
[SUCCESS] Database connection SUCCESSFUL!

PostgreSQL Information:
----------------------------------------------------------------------
  Version: PostgreSQL 16.x
  Database: hms_test
  Server Address: 127.0.0.1
  Server Port: 5432
  [WARNING] SSL: Not active (Unencrypted)
  Active Connections: 1

======================================================================
[SUCCESS] ALL CHECKS PASSED!
======================================================================
```

---

### Step 7: Migrate Your Database

```powershell
# Create all tables in PostgreSQL
python manage.py migrate

# Expected output:
# Running migrations:
#   Applying contenttypes.0001_initial... OK
#   Applying auth.0001_initial... OK
#   ...
#   Applying hospital.0001_initial... OK
```

---

### Step 8: (Optional) Import Existing Data

If you want to migrate data from SQLite to PostgreSQL:

```powershell
# Export data from SQLite
python manage.py dumpdata --natural-foreign --natural-primary --exclude=contenttypes --exclude=auth.permission > data_backup.json

# Change DATABASE_URL to PostgreSQL (already done in .env)

# Import data to PostgreSQL
python manage.py loaddata data_backup.json
```

**Note:** You may need to import in batches if you have a lot of data:

```powershell
# Export specific apps
python manage.py dumpdata hospital.Patient > patients.json
python manage.py dumpdata hospital.Staff > staff.json

# Import them
python manage.py loaddata patients.json
python manage.py loaddata staff.json
```

---

### Step 9: Create Superuser

```powershell
# Create admin user for Django
python manage.py createsuperuser

# Enter username, email, and password when prompted
```

---

### Step 10: Start the Server

```powershell
# Stop the old server if running (Ctrl+C)

# Start with PostgreSQL
python manage.py runserver
```

---

## 🎯 Verify Everything Works

### Test 1: Check Database Connection

```powershell
python manage.py check --database default
```

Should show: `System check identified no issues (0 silenced).`

### Test 2: Access Django Shell

```powershell
python manage.py dbshell
```

You should see the PostgreSQL prompt:

```
hms_test=>
```

Try a query:

```sql
\dt
-- Lists all tables

SELECT COUNT(*) FROM hospital_patient;
-- Shows patient count

\q
-- Exit
```

### Test 3: Access Admin Panel

1. Open browser: http://127.0.0.1:8000/admin/
2. Login with superuser credentials
3. Check that data loads correctly

### Test 4: Access Patient List

1. Open: http://127.0.0.1:8000/hms/patients/
2. Verify patients are showing
3. Test search and filtering

---

## 📊 Compare Performance: SQLite vs PostgreSQL

### SQLite (Before)

```powershell
# Using SQLite
DATABASE_URL=sqlite:///db.sqlite3
```

- ✅ Simple, no installation needed
- ❌ Limited concurrent access
- ❌ No advanced features
- ❌ Not suitable for production

### PostgreSQL (After)

```powershell
# Using PostgreSQL
DATABASE_URL=postgresql://hms_user:hms_password_123@localhost:5432/hms_test
```

- ✅ Production-ready
- ✅ Handles concurrent users
- ✅ Advanced features (JSON, full-text search, etc.)
- ✅ Better performance with large datasets
- ✅ Can scale to remote server easily

---

## 🔍 Monitoring Your PostgreSQL Database

### Using pgAdmin

1. Open pgAdmin 4
2. Connect to your server
3. Navigate to: Databases → hms_test → Schemas → public → Tables
4. Right-click any table → "View/Edit Data" → "All Rows"

### Check Database Size

```sql
-- In psql or pgAdmin Query Tool
SELECT pg_size_pretty(pg_database_size('hms_test')) AS size;
```

### Check Active Connections

```sql
SELECT count(*) FROM pg_stat_activity WHERE datname = 'hms_test';
```

### View Tables and Row Counts

```sql
SELECT 
    schemaname,
    tablename,
    n_tup_ins as inserts,
    n_tup_upd as updates,
    n_tup_del as deletes
FROM pg_stat_user_tables
ORDER BY tablename;
```

---

## 🚀 Next Steps: Simulate True Remote Connection

To make this even more realistic, you can:

### Option 1: Use IP Address Instead of localhost

```bash
# In .env
DATABASE_URL=postgresql://hms_user:hms_password_123@127.0.0.1:5432/hms_test
```

### Option 2: Configure PostgreSQL to Listen on Network

Edit `postgresql.conf`:

```
# Location: C:\Program Files\PostgreSQL\16\data\postgresql.conf

# Change:
listen_addresses = 'localhost'

# To:
listen_addresses = '*'  # Listen on all network interfaces
```

Edit `pg_hba.conf`:

```
# Location: C:\Program Files\PostgreSQL\16\data\pg_hba.conf

# Add:
host    hms_test    hms_user    127.0.0.1/32    scram-sha-256
host    hms_test    hms_user    0.0.0.0/0       scram-sha-256  # Allow from any IP
```

Restart PostgreSQL:

```powershell
Restart-Service postgresql-x64-16
```

### Option 3: Test with Docker PostgreSQL

If you have Docker installed:

```powershell
# Run PostgreSQL in Docker
docker run --name postgres-test -e POSTGRES_PASSWORD=admin123 -e POSTGRES_DB=hms_test -p 5432:5432 -d postgres:16

# Connect to it
DATABASE_URL=postgresql://postgres:admin123@localhost:5432/hms_test
```

---

## 🔧 Troubleshooting

### Problem: Can't connect to PostgreSQL

**Check if service is running:**

```powershell
Get-Service postgresql*
```

**Start if stopped:**

```powershell
Start-Service postgresql-x64-16
```

### Problem: Authentication failed

**Reset password:**

```powershell
# Connect as postgres superuser
cd "C:\Program Files\PostgreSQL\16\bin"
.\psql.exe -U postgres

# Change password
ALTER USER hms_user WITH PASSWORD 'new_password';
```

### Problem: psycopg2 installation fails

**Try precompiled binary:**

```powershell
pip uninstall psycopg2 psycopg2-binary
pip install psycopg2-binary
```

### Problem: "database does not exist"

**Create it:**

```sql
-- In psql as postgres user
CREATE DATABASE hms_test;
```

### Problem: "permission denied for schema public"

**Grant permissions:**

```sql
-- In psql connected to hms_test database
GRANT ALL ON SCHEMA public TO hms_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO hms_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO hms_user;
```

---

## 📚 Useful PostgreSQL Commands

```sql
-- List databases
\l

-- Connect to database
\c hms_test

-- List tables
\dt

-- Describe table
\d hospital_patient

-- List users
\du

-- Show current user
SELECT current_user;

-- Show database size
SELECT pg_size_pretty(pg_database_size(current_database()));

-- Show table sizes
SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Quit
\q
```

---

## ✅ Success Checklist

- [ ] PostgreSQL installed and running
- [ ] hms_test database created
- [ ] hms_user created with correct password
- [ ] Permissions granted
- [ ] psycopg2-binary installed
- [ ] .env updated with DATABASE_URL
- [ ] Connection test successful
- [ ] Migrations run successfully
- [ ] Superuser created
- [ ] Server started and working
- [ ] Can access admin panel
- [ ] Can access patient list
- [ ] Data showing correctly

---

## 🎉 Congratulations!

You now have:

- ✅ PostgreSQL server running locally
- ✅ HMS connected to PostgreSQL (simulating remote setup)
- ✅ All data migrated and working
- ✅ Production-ready database architecture
- ✅ Ready to scale to true remote server

**Next:** When ready for production, simply change the DATABASE_URL to point to your actual remote PostgreSQL server!

```bash
# Development (local)
DATABASE_URL=postgresql://hms_user:password@localhost:5432/hms_test

# Production (remote)
DATABASE_URL=postgresql://hms_user:password@192.168.1.20:5432/hms_production
```

The code remains exactly the same! 🚀

