# Quick Connect Guide - GitHub to VPS

## VPS Connection Details
- **IP**: 45.8.225.73
- **User**: root
- **Password**: kaqA!S*eM9)q

## Step 1: Connect via PuTTY

1. Open PuTTY
2. Enter: `45.8.225.73`
3. Port: `22`
4. Click "Open"
5. Login: `root`
6. Password: `kaqA!S*eM9)q`

## Step 2: Clone Your Repository

Once connected, run:

```bash
# Navigate to your project directory (or create one)
cd /opt/hms || cd ~
mkdir -p primemed
cd primemed

# Clone repository
git clone https://github.com/jerry6193/primemed.git .

# Or if directory exists, just clone
git clone https://github.com/jerry6193/primemed.git
cd primemed
```

**When prompted for GitHub credentials:**
- Username: `jerry6193`
- Password: Use a **Personal Access Token** (not your GitHub password)

**To create token:**
1. Go to: https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select `repo` permission
4. Copy the token and use it as password

## Step 3: Set Up Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

## Step 4: Configure Environment

```bash
# Create .env file
nano .env
```

Add:
```env
DEBUG=False
SECRET_KEY=your-secret-key-here-generate-with-django
DATABASE_URL=postgresql://hms_user:password@localhost:5432/hms_db
ALLOWED_HOSTS=45.8.225.73
```

**Generate SECRET_KEY:**
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## Step 5: Set Up Database

```bash
# Create database (if not exists)
sudo -u postgres psql
CREATE DATABASE hms_db;
CREATE USER hms_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE hms_db TO hms_user;
\q

# Run migrations
python manage.py migrate
python manage.py collectstatic --noinput
```

## Step 6: Test Run

```bash
# Test if everything works
python manage.py runserver 0.0.0.0:8000
```

Visit: `http://45.8.225.73:8000`

## Step 7: Set Up Production Server (Gunicorn)

```bash
# Install gunicorn
pip install gunicorn

# Run with gunicorn
gunicorn --bind 0.0.0.0:8000 hms.wsgi:application
```

## Quick Update Commands

After initial setup, to update from GitHub:

```bash
cd /opt/hms/primemed  # or wherever you cloned
source venv/bin/activate
git pull origin main
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
# Restart your server (gunicorn/systemd)
```

## Troubleshooting

**Can't clone?**
- Use Personal Access Token instead of password
- Or set up SSH key: `ssh-keygen -t ed25519` then add to GitHub

**Permission denied?**
- Use `sudo` if needed
- Check file permissions: `chmod -R 755 /opt/hms`

**Database errors?**
- Check PostgreSQL is running: `sudo systemctl status postgresql`
- Verify DATABASE_URL in .env

**Port already in use?**
- Check what's using port 8000: `sudo lsof -i :8000`
- Kill process or use different port







