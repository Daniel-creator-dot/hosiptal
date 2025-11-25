# VPS Setup Steps - After Git Clone

## Current Status
✅ Repository cloned to: `/root/primemed`

## Step 1: Check for Errors

Run this command on your VPS:

```bash
cd ~/primemed
bash check_and_setup.sh
```

Or manually check:

```bash
# Check if you're in the right directory
ls -la manage.py

# Check Python
python3 --version

# Check PostgreSQL
sudo systemctl status postgresql
```

## Step 2: Set Up Virtual Environment

```bash
cd ~/primemed

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Verify activation (should show venv path)
which python
```

## Step 3: Install Dependencies

```bash
# Make sure venv is activated (you should see (venv) in prompt)
pip install --upgrade pip
pip install -r requirements.txt
```

**If you get errors:**
- Missing system packages: `sudo apt install python3-dev libpq-dev`
- Permission errors: Make sure venv is activated

## Step 4: Configure Environment

```bash
# Create .env file
nano .env
```

Add:
```env
DEBUG=False
SECRET_KEY=generate-with-command-below
DATABASE_URL=postgresql://hms_user:your_password@localhost:5432/hms_db
ALLOWED_HOSTS=45.8.225.73
```

**Generate SECRET_KEY:**
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## Step 5: Set Up Database

```bash
# Create database user and database
sudo -u postgres psql
```

In PostgreSQL prompt:
```sql
CREATE DATABASE hms_db;
CREATE USER hms_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE hms_db TO hms_user;
ALTER USER hms_user CREATEDB;
\q
```

Update `.env` with the password you set.

## Step 6: Run Migrations

```bash
# Make sure venv is activated
source venv/bin/activate

# Run migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput
```

## Step 7: Test Run

```bash
# Run development server
python manage.py runserver 0.0.0.0:8000
```

Visit: `http://45.8.225.73:8000`

## Common Errors & Fixes

### Error: "No module named 'django'"
**Fix:**
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Error: "psycopg2" installation fails
**Fix:**
```bash
sudo apt install python3-dev libpq-dev
pip install psycopg2-binary
```

### Error: "Database connection failed"
**Fix:**
- Check PostgreSQL is running: `sudo systemctl start postgresql`
- Verify DATABASE_URL in .env
- Check database exists: `sudo -u postgres psql -l`

### Error: "ALLOWED_HOSTS" error
**Fix:**
- Add your IP to ALLOWED_HOSTS in .env: `ALLOWED_HOSTS=45.8.225.73`

### Error: "Permission denied"
**Fix:**
- Check file permissions: `chmod -R 755 ~/primemed`
- Use sudo if needed for system commands

## Quick Status Check

```bash
cd ~/primemed
source venv/bin/activate
python manage.py check
```

This will show any configuration errors.

## Production Setup (After Testing)

Once everything works, set up Gunicorn:

```bash
pip install gunicorn
gunicorn --bind 0.0.0.0:8000 hms.wsgi:application
```

Then configure Nginx as reverse proxy (see VPS_DEPLOYMENT_GUIDE.md)







