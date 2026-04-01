# PostgreSQL Authentication Fix Guide

## Error Message
```
django.db.utils.OperationalError: connection to server at "localhost" (::1), port 5432 failed: 
FATAL: password authentication failed for user "hms_user"
```

## Problem
Your Django application is trying to connect to PostgreSQL with:
- **User**: `hms_user`
- **Password**: `hms_password`
- **Database**: `hms_db`
- **Host**: `localhost:5432`

But PostgreSQL is rejecting the connection because either:
1. The user `hms_user` doesn't exist
2. The password is incorrect
3. The user exists but has a different password

## Solutions

### Solution 1: Automatic Fix (Recommended)
Run the automated fix script:
```batch
FIX_POSTGRESQL_AUTH.bat
```

This script will:
- Connect to PostgreSQL as `postgres` superuser
- Create `hms_user` if it doesn't exist
- Set password to `hms_password`
- Create `hms_db` database if it doesn't exist
- Grant all necessary privileges

**Note**: You'll need to enter the PostgreSQL `postgres` user password (the one you set during installation).

### Solution 2: Manual Fix Using pgAdmin (GUI)
Run the simple guide:
```batch
FIX_POSTGRESQL_AUTH_SIMPLE.bat
```

Or follow these steps manually:

1. **Open pgAdmin**
   - Search for "pgAdmin" in Start Menu
   - Or open PostgreSQL Desktop application

2. **Connect to PostgreSQL Server**
   - Expand your PostgreSQL server in the left sidebar
   - Enter password when prompted (your PostgreSQL installation password)

3. **Create/Update User**
   - Expand "Login/Group Roles"
   - If `hms_user` exists:
     - Right-click `hms_user` → Properties → Definition tab
     - Set Password to: `hms_password`
     - Click Save
   - If `hms_user` doesn't exist:
     - Right-click "Login/Group Roles" → Create → Login/Group Role
     - General tab: Name = `hms_user`
     - Definition tab: Password = `hms_password`
     - Privileges tab: Check "Can login?"
     - Click Save

4. **Create Database**
   - Right-click "Databases" → Create → Database
   - Name: `hms_db`
   - Owner: `hms_user` (or `postgres`)
   - Click Save

5. **Grant Privileges** (if database owner is `postgres`)
   - Right-click `hms_db` → Query Tool
   - Run these SQL commands:
     ```sql
     GRANT ALL ON SCHEMA public TO hms_user;
     ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO hms_user;
     ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO hms_user;
     ```

### Solution 3: Use Command Line (psql)

If you have `psql` in your PATH:

```batch
psql -U postgres
```

Then run these SQL commands:
```sql
-- Create user if not exists, or update password if exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = 'hms_user') THEN
        CREATE USER hms_user WITH PASSWORD 'hms_password';
    ELSE
        ALTER USER hms_user WITH PASSWORD 'hms_password';
    END IF;
END
$$;

-- Create database if not exists
SELECT 'CREATE DATABASE hms_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'hms_db')\gexec

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE hms_db TO hms_user;

-- Connect to database and grant schema privileges
\c hms_db
GRANT ALL ON SCHEMA public TO hms_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO hms_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO hms_user;

-- Set user properties
\c postgres
ALTER ROLE hms_user SET client_encoding TO 'utf8';
ALTER ROLE hms_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE hms_user SET timezone TO 'UTC';

\q
```

## Verify Configuration

### Check .env File
Your `.env` file should have:
```bash
DATABASE_URL=postgresql://hms_user:hms_password@localhost:5432/hms_db
```

### Test Connection
After fixing, test the connection:
```batch
python manage.py migrate --dry-run
```

Or use the database shell:
```batch
python manage.py dbshell
```

If successful, you should see the PostgreSQL prompt: `hms_db=#`

## Common Issues

### Issue 1: PostgreSQL Service Not Running
**Symptom**: Connection refused or "could not connect to server"

**Fix**:
1. Open Services: `services.msc`
2. Find "postgresql" service
3. Right-click → Start

### Issue 2: Can't Find psql Command
**Symptom**: `'psql' is not recognized as an internal or external command`

**Fix**:
- Add PostgreSQL bin directory to PATH:
  - `C:\Program Files\PostgreSQL\15\bin`
  - `C:\Program Files\PostgreSQL\16\bin`
- Or use full path: `"C:\Program Files\PostgreSQL\15\bin\psql.exe" -U postgres`

### Issue 3: Don't Know postgres Password
**Symptom**: Can't connect as postgres user

**Fix**:
1. Try common default passwords: `postgres`, `admin`, `password`
2. Check if you wrote it down during installation
3. If all else fails, you may need to reset PostgreSQL password (requires service restart)

### Issue 4: Using Different User/Password
If you want to use a different PostgreSQL user (e.g., `postgres` with a different password):

1. Update `.env` file:
   ```bash
   DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/hms_db
   ```

2. Create database:
   ```sql
   CREATE DATABASE hms_db;
   ```

## After Fixing

Once authentication is fixed:

1. **Run Migrations**:
   ```batch
   python manage.py migrate
   ```

2. **Create Superuser** (if needed):
   ```batch
   python manage.py createsuperuser
   ```

3. **Start Server**:
   ```batch
   python manage.py runserver
   ```

## Still Having Issues?

If none of the above solutions work:

1. **Check PostgreSQL Logs**:
   - Location: `C:\Program Files\PostgreSQL\15\data\log\`
   - Or check Windows Event Viewer → Applications → PostgreSQL

2. **Verify PostgreSQL is Listening**:
   ```batch
   netstat -an | findstr 5432
   ```
   Should show: `0.0.0.0:5432` or `127.0.0.1:5432`

3. **Check pg_hba.conf**:
   - Location: `C:\Program Files\PostgreSQL\15\data\pg_hba.conf`
   - Should have: `host    all    all    127.0.0.1/32    md5`

4. **Contact Support**:
   - Provide the exact error message
   - Include PostgreSQL version
   - Include what you've tried



