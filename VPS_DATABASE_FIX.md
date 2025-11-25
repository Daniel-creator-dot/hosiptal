# VPS Database Fix Guide

## Quick Fix Script

Run this on your VPS:

```bash
cd /var/www/chm
bash fix_database_vps.sh
```

## Manual Troubleshooting

### Step 1: Check PostgreSQL Service

```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# If not running, start it
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### Step 2: Check Database Connection

```bash
cd /var/www/chm
source venv/bin/activate
python check_database.py
```

### Step 3: Verify Database Configuration

Check your `.env` file:

```bash
cd /var/www/chm
cat .env | grep DATABASE_URL
```

Should look like:
```
DATABASE_URL=postgresql://hms_user:password@localhost:5432/hms_db
```

### Step 4: Create Database (if missing)

```bash
sudo -u postgres psql
```

In PostgreSQL prompt:
```sql
-- Check if database exists
\l

-- If database doesn't exist, create it
CREATE DATABASE hms_db;

-- Create user (if doesn't exist)
CREATE USER hms_user WITH PASSWORD 'your_secure_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE hms_db TO hms_user;
ALTER USER hms_user CREATEDB;

-- Exit
\q
```

### Step 5: Update .env File

```bash
cd /var/www/chm
nano .env
```

Update DATABASE_URL:
```env
DATABASE_URL=postgresql://hms_user:your_secure_password@localhost:5432/hms_db
```

### Step 6: Test Connection

```bash
cd /var/www/chm
source venv/bin/activate
python manage.py dbshell
```

If this works, you should see PostgreSQL prompt. Type `\q` to exit.

### Step 7: Run Migrations

```bash
cd /var/www/chm
source venv/bin/activate
python manage.py migrate
```

### Step 8: Create Superuser (if needed)

```bash
python manage.py createsuperuser
```

Enter:
- Username
- Email (optional)
- Password (twice)

### Step 9: Restart Services

```bash
sudo systemctl restart gunicorn-chm.service
sudo systemctl status gunicorn-chm.service
```

## Common Issues

### Issue 1: "FATAL: password authentication failed"

**Fix:**
```bash
# Reset PostgreSQL password
sudo -u postgres psql
ALTER USER hms_user WITH PASSWORD 'new_password';
\q

# Update .env file
nano .env
# Update DATABASE_URL with new password
```

### Issue 2: "FATAL: database does not exist"

**Fix:**
```bash
sudo -u postgres createdb hms_db
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE hms_db TO hms_user;"
```

### Issue 3: "FATAL: role does not exist"

**Fix:**
```bash
sudo -u postgres psql
CREATE USER hms_user WITH PASSWORD 'password';
ALTER USER hms_user CREATEDB;
GRANT ALL PRIVILEGES ON DATABASE hms_db TO hms_user;
\q
```

### Issue 4: "Connection refused"

**Fix:**
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Check if listening on port 5432
sudo netstat -tlnp | grep 5432

# Check PostgreSQL config
sudo nano /etc/postgresql/*/main/postgresql.conf
# Ensure: listen_addresses = 'localhost' or '*'

# Check pg_hba.conf
sudo nano /etc/postgresql/*/main/pg_hba.conf
# Ensure local connections are allowed:
# local   all             all                                     md5
# host    all             all             127.0.0.1/32            md5

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### Issue 5: "No module named 'psycopg2'"

**Fix:**
```bash
cd /var/www/chm
source venv/bin/activate
pip install psycopg2-binary
```

### Issue 6: "relation does not exist" (after migrations)

**Fix:**
```bash
cd /var/www/chm
source venv/bin/activate
python manage.py migrate --run-syncdb
```

## Quick Diagnostic Commands

```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Check database exists
sudo -u postgres psql -l

# Check users
sudo -u postgres psql -c "\du"

# Test connection
sudo -u postgres psql -d hms_db -U hms_user

# Check Django database connection
cd /var/www/chm
source venv/bin/activate
python manage.py dbshell

# Run diagnostic script
python check_database.py
```

## Complete Reset (Last Resort)

If nothing works, reset the database:

```bash
# WARNING: This will delete all data!
cd /var/www/chm
source venv/bin/activate

# Drop and recreate database
sudo -u postgres psql <<EOF
DROP DATABASE IF EXISTS hms_db;
CREATE DATABASE hms_db;
GRANT ALL PRIVILEGES ON DATABASE hms_db TO hms_user;
\q
EOF

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static
python manage.py collectstatic --noinput

# Restart service
sudo systemctl restart gunicorn-chm.service
```

## After Fixing

1. Test login at: `http://your-vps-ip/hms/login/`
2. Check logs: `sudo journalctl -u gunicorn-chm.service -f`
3. Check database: `python check_database.py`







