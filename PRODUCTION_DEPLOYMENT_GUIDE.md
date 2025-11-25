# 🚀 HMS PRODUCTION DEPLOYMENT GUIDE

## ✅ **Complete Guide to Deploy HMS to Production Server with PostgreSQL**

---

## 📋 **Prerequisites**

### **Server Requirements:**
- **OS:** Ubuntu 20.04 LTS or newer (or Debian-based Linux)
- **RAM:** Minimum 2GB (4GB+ recommended)
- **CPU:** 2+ cores recommended
- **Storage:** 20GB+ free space
- **Network:** Static IP or domain name

### **Software Needed:**
- PostgreSQL 13+
- Python 3.10+
- Nginx (for reverse proxy)
- Supervisor (for process management)
- Redis (for caching)

---

## 🎯 **Deployment Steps**

### **STEP 1: Prepare Your Server**

```bash
# SSH into your server
ssh user@your-server-ip

# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install required packages
sudo apt-get install -y python3-pip python3-dev libpq-dev nginx supervisor git redis-server
```

---

### **STEP 2: Install PostgreSQL**

```bash
# Install PostgreSQL
sudo apt-get install -y postgresql postgresql-contrib

# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
sudo -u postgres psql << EOF
CREATE DATABASE hms_production;
CREATE USER hms_user WITH PASSWORD 'your_secure_password_here';
ALTER ROLE hms_user SET client_encoding TO 'utf8';
ALTER ROLE hms_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE hms_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE hms_production TO hms_user;
\c hms_production
GRANT ALL ON SCHEMA public TO hms_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO hms_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO hms_user;
\q
EOF
```

---

### **STEP 3: Upload Your HMS Project**

**Option A: Using Git (Recommended)**
```bash
cd /var/www/
sudo git clone https://github.com/yourusername/hms.git
sudo chown -R www-data:www-data hms
cd hms
```

**Option B: Using SCP/SFTP**
```bash
# From your local machine:
scp -r C:\Users\user\chm user@your-server:/tmp/hms

# On server:
sudo mv /tmp/hms /var/www/
sudo chown -R www-data:www-data /var/www/hms
cd /var/www/hms
```

---

### **STEP 4: Set Up Python Environment**

```bash
cd /var/www/hms

# Install virtualenv
sudo pip3 install virtualenv

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

---

### **STEP 5: Configure Environment Variables**

```bash
# Create .env file
nano .env
```

**Paste this (update values):**
```bash
# Django Settings
SECRET_KEY=generate-a-very-long-random-secret-key-here-min-50-characters
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com,your-server-ip

# Database
DATABASE_URL=postgresql://hms_user:your_secure_password_here@localhost:5432/hms_production

# Redis
REDIS_URL=redis://localhost:6379/0
USE_REDIS_CACHE=True

# Static Files
STATIC_ROOT=/var/www/hms/staticfiles/
MEDIA_ROOT=/var/www/hms/media/
```

**Generate SECRET_KEY:**
```python
# In Python shell:
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

### **STEP 6: Migrate Data to PostgreSQL**

**Option A: Fresh Installation (New System)**
```bash
# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput
```

**Option B: Migrate from SQLite (Keep Your Data)**
```bash
# Export from SQLite (already done if you ran migrate_to_postgresql.py)
# Upload hms_data_export.json to server

# Run migrations first
python manage.py migrate

# Import data
python import_to_postgresql.py

# Create additional superuser if needed
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput
```

---

### **STEP 7: Configure Gunicorn**

```bash
# Create Gunicorn config
sudo nano /etc/supervisor/conf.d/hms.conf
```

**Paste this:**
```ini
[program:hms]
directory=/var/www/hms
command=/var/www/hms/venv/bin/gunicorn hms.wsgi:application --bind 0.0.0.0:8000 --workers 4 --timeout 120
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/hms/gunicorn.log
stderr_logfile=/var/log/hms/gunicorn-error.log
environment=PATH="/var/www/hms/venv/bin"
```

**Create log directory:**
```bash
sudo mkdir -p /var/log/hms
sudo chown www-data:www-data /var/log/hms
```

---

### **STEP 8: Configure Nginx**

```bash
# Create Nginx config
sudo nano /etc/nginx/sites-available/hms
```

**Paste this:**
```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    client_max_body_size 100M;

    location /static/ {
        alias /var/www/hms/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /var/www/hms/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 300s;
        proxy_read_timeout 300s;
    }
}
```

**Enable site:**
```bash
sudo ln -s /etc/nginx/sites-available/hms /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

### **STEP 9: Set Up SSL/HTTPS (Recommended)**

```bash
# Install Certbot
sudo apt-get install -y certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# Auto-renewal (already set up by certbot)
sudo certbot renew --dry-run
```

---

### **STEP 10: Start Services**

```bash
# Start Supervisor
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start hms

# Check status
sudo supervisorctl status hms

# View logs
sudo tail -f /var/log/hms/gunicorn.log
```

---

## 🔧 **Production Settings Configuration**

### **Update hms/settings.py:**

```python
import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

load_dotenv()

# Security
SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = os.getenv('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')

# Database
DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Redis Cache
if os.getenv('USE_REDIS_CACHE', 'False') == 'True':
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0'),
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'SOCKET_CONNECT_TIMEOUT': 5,
                'SOCKET_TIMEOUT': 5,
                'CONNECTION_POOL_KWARGS': {'max_connections': 50}
            }
        }
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'

# Static files (production)
STATIC_ROOT = os.getenv('STATIC_ROOT', BASE_DIR / 'staticfiles')
MEDIA_ROOT = os.getenv('MEDIA_ROOT', BASE_DIR / 'media')
STATIC_URL = '/static/'
MEDIA_URL = '/media/'

# Static files serving with WhiteNoise
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Security (production only)
if not DEBUG:
    SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'True') == 'True'
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Logging (production)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': '/var/log/hms/django-errors.log',
        },
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}
```

---

## 📦 **Files to Upload to Server**

### **Required Files:**
1. ✅ **All project files** (entire chm folder)
2. ✅ **requirements.txt** (Python dependencies)
3. ✅ **hms_data_export.json** (your data - if migrating)
4. ✅ **setup_postgresql_production.sh** (PostgreSQL setup)
5. ✅ **import_to_postgresql.py** (data import)
6. ✅ **PRODUCTION_ENV_TEMPLATE.txt** (configuration template)

### **Do NOT Upload:**
- ❌ **db.sqlite3** (use PostgreSQL instead)
- ❌ **__pycache__** folders (auto-generated)
- ❌ **.git** folder (if using git on server)
- ❌ **venv** folder (create fresh on server)
- ❌ **.env** file (create fresh with production values)

---

## 🔐 **Security Checklist**

### **Before Going Live:**

- [ ] Set `DEBUG = False` in .env
- [ ] Generate new SECRET_KEY (different from development)
- [ ] Set proper ALLOWED_HOSTS
- [ ] Change PostgreSQL password from default
- [ ] Set up HTTPS/SSL with Let's Encrypt
- [ ] Configure firewall (ufw)
- [ ] Set up regular backups
- [ ] Configure Redis password
- [ ] Enable Django security headers
- [ ] Set up monitoring (Sentry)

---

## 🛡️ **Firewall Configuration**

```bash
# Enable firewall
sudo ufw enable

# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Check status
sudo ufw status
```

---

## 💾 **Backup Configuration**

### **Daily Automated Backups:**

```bash
# Create backup script
sudo nano /usr/local/bin/backup-hms.sh
```

**Paste this:**
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/hms"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup PostgreSQL database
sudo -u postgres pg_dump hms_production | gzip > $BACKUP_DIR/hms_db_$DATE.sql.gz

# Backup media files
tar -czf $BACKUP_DIR/hms_media_$DATE.tar.gz /var/www/hms/media/

# Delete backups older than 30 days
find $BACKUP_DIR -type f -mtime +30 -delete

echo "Backup completed: $DATE"
```

**Make executable and schedule:**
```bash
sudo chmod +x /usr/local/bin/backup-hms.sh

# Add to crontab (daily at 2 AM)
sudo crontab -e
# Add this line:
0 2 * * * /usr/local/bin/backup-hms.sh
```

---

## 📊 **Monitoring & Logs**

### **View Logs:**
```bash
# Django logs
sudo tail -f /var/log/hms/django-errors.log

# Gunicorn logs
sudo tail -f /var/log/hms/gunicorn.log

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-*-main.log
```

### **Monitor System:**
```bash
# Check services
sudo supervisorctl status

# Check Nginx
sudo systemctl status nginx

# Check PostgreSQL
sudo systemctl status postgresql

# Check Redis
sudo systemctl status redis-server
```

---

## 🚀 **Quick Deployment Commands**

### **On Your Local Machine:**

```bash
# Step 1: Export data
python migrate_to_postgresql.py

# Step 2: Upload to server
scp -r C:\Users\user\chm user@your-server:/tmp/hms
scp hms_data_export.json user@your-server:/tmp/
```

---

### **On Your Server:**

```bash
# Step 1: Move files
sudo mv /tmp/hms /var/www/
sudo mv /tmp/hms_data_export.json /var/www/hms/
cd /var/www/hms

# Step 2: Set permissions
sudo chown -R www-data:www-data /var/www/hms

# Step 3: Setup PostgreSQL
sudo bash setup_postgresql_production.sh

# Step 4: Create Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Step 5: Configure environment
cp PRODUCTION_ENV_TEMPLATE.txt .env
nano .env  # Update with your values

# Step 6: Run migrations
python manage.py migrate

# Step 7: Import data (if migrating from SQLite)
python import_to_postgresql.py

# Step 8: Create superuser
python manage.py createsuperuser

# Step 9: Collect static files
python manage.py collectstatic --noinput

# Step 10: Configure services
sudo cp deployment/hms.conf /etc/supervisor/conf.d/
sudo cp deployment/hms-nginx.conf /etc/nginx/sites-available/hms
sudo ln -s /etc/nginx/sites-available/hms /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start hms

# Step 11: Setup SSL
sudo certbot --nginx -d your-domain.com

# Done!
```

---

## 🔧 **Performance Tuning**

### **PostgreSQL Optimization:**

```bash
sudo nano /etc/postgresql/*/main/postgresql.conf
```

**Add these settings:**
```
# Connection Settings
max_connections = 200

# Memory Settings  
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 128MB
work_mem = 4MB

# Query Performance
random_page_cost = 1.1
effective_io_concurrency = 200

# WAL Settings
wal_buffers = 16MB
min_wal_size = 1GB
max_wal_size = 4GB

# Autovacuum
autovacuum = on
autovacuum_max_workers = 3
```

**Restart PostgreSQL:**
```bash
sudo systemctl restart postgresql
```

---

### **Gunicorn Workers:**

Calculate optimal workers:
```
workers = (2 x CPU_cores) + 1

For 2 cores: 5 workers
For 4 cores: 9 workers
```

---

## 📊 **Testing Your Production Deployment**

### **Test Checklist:**

```bash
# 1. Test Django
python manage.py check --deploy

# 2. Test database connection
python manage.py dbshell
\dt  # List tables
\q

# 3. Test static files
python manage.py collectstatic --noinput

# 4. Test Gunicorn
gunicorn hms.wsgi:application --bind 127.0.0.1:8000 --workers 2

# 5. Access your site
curl http://your-server-ip/hms/

# 6. Check all services
sudo supervisorctl status
sudo systemctl status nginx
sudo systemctl status postgresql
sudo systemctl status redis-server
```

---

## 🎯 **Post-Deployment**

### **First-Time Setup:**

1. **Access Admin Panel:**
   ```
   https://your-domain.com/admin/
   ```

2. **Create Staff Accounts**

3. **Configure Services:**
   - Add departments
   - Add ambulance units
   - Configure service charges
   - Set up appointments

4. **Test Core Functions:**
   - Register test patient
   - Create appointment
   - Process payment
   - Generate reports

---

## 🔒 **Maintenance**

### **Daily:**
- Check error logs
- Monitor performance
- Review user activity

### **Weekly:**
- Review backup success
- Check disk space
- Update security patches

### **Monthly:**
- Database vacuum/analyze
- Review and rotate logs
- Performance analysis

---

## 📱 **Access URLs**

### **Production:**
```
Website:        https://your-domain.com/hms/
Admin:          https://your-domain.com/admin/
API:            https://your-domain.com/api/
```

---

## 🆘 **Troubleshooting**

### **Service Not Starting:**
```bash
# Check logs
sudo supervisorctl tail hms stderr

# Restart service
sudo supervisorctl restart hms

# Check Nginx
sudo nginx -t
sudo systemctl restart nginx
```

### **Database Connection Error:**
```bash
# Test connection
psql -U hms_user -d hms_production -h localhost

# Check PostgreSQL status
sudo systemctl status postgresql

# Check .env file
cat .env | grep DATABASE_URL
```

### **Static Files Not Loading:**
```bash
# Recollect static files
python manage.py collectstatic --noinput --clear

# Check permissions
sudo chown -R www-data:www-data /var/www/hms/staticfiles/

# Restart Nginx
sudo systemctl restart nginx
```

---

## 🎉 **Deployment Complete!**

```
╔════════════════════════════════════════════════╗
║     HMS PRODUCTION DEPLOYMENT                  ║
╠════════════════════════════════════════════════╣
║                                                ║
║  ✅ PostgreSQL Database                        ║
║  ✅ Gunicorn WSGI Server                       ║
║  ✅ Nginx Reverse Proxy                        ║
║  ✅ SSL/HTTPS Security                         ║
║  ✅ Redis Caching                              ║
║  ✅ Automated Backups                          ║
║  ✅ Process Management (Supervisor)            ║
║  ✅ Static File Serving                        ║
║  ✅ Production Optimizations                   ║
║                                                ║
║  Status: PRODUCTION-READY ✅                   ║
║                                                ║
╚════════════════════════════════════════════════╝
```

**Your HMS is now running on a production server with PostgreSQL!** 🚀

**Access:** `https://your-domain.com/hms/`

---

## 📚 **Additional Resources**

### **Created Files:**
- ✅ **requirements.txt** - All dependencies
- ✅ **migrate_to_postgresql.py** - Data export script
- ✅ **import_to_postgresql.py** - Data import script
- ✅ **setup_postgresql_production.sh** - PostgreSQL setup
- ✅ **PRODUCTION_ENV_TEMPLATE.txt** - Environment variables
- ✅ **PRODUCTION_DEPLOYMENT_GUIDE.md** - This guide

### **Support:**
- Django Documentation: https://docs.djangoproject.com/
- PostgreSQL Docs: https://www.postgresql.org/docs/
- Gunicorn Guide: https://docs.gunicorn.org/
- Nginx Documentation: https://nginx.org/en/docs/

---

**Your HMS is ready for production deployment!** 🎊

















