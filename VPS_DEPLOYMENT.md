# VPS Deployment Guide

## Quick Deploy

Run this single command on your VPS:

```bash
cd /var/www/chm && bash deploy.sh
```

## Manual Deployment Steps

If you prefer to run commands manually:

```bash
# 1. Navigate to project directory
cd /var/www/chm

# 2. Pull latest changes
git pull origin main

# 3. Activate virtual environment
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run migrations
python manage.py migrate

# 6. Collect static files
python manage.py collectstatic --noinput

# 7. Restart Gunicorn service
sudo systemctl restart gunicorn-chm.service
```

## Setup Instructions (First Time)

If `/var/www/chm` doesn't exist yet:

```bash
# Create directory
sudo mkdir -p /var/www/chm
sudo chown $USER:$USER /var/www/chm

# Clone repository
cd /var/www
git clone https://github.com/jerry6193/primemed.git chm
cd chm

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Configure environment
nano .env
# Add your settings: DEBUG=False, SECRET_KEY=..., DATABASE_URL=..., ALLOWED_HOSTS=...

# Run migrations
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

## Gunicorn Service Setup

Create systemd service file:

```bash
sudo nano /etc/systemd/system/gunicorn-chm.service
```

Add this content:

```ini
[Unit]
Description=Gunicorn service for CHM HMS
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/chm
Environment="PATH=/var/www/chm/venv/bin"
ExecStart=/var/www/chm/venv/bin/gunicorn \
    --bind 127.0.0.1:8000 \
    --workers 3 \
    --timeout 120 \
    --access-logfile /var/log/gunicorn-chm-access.log \
    --error-logfile /var/log/gunicorn-chm-error.log \
    hms.wsgi:application

[Install]
WantedBy=multi-user.target
```

Enable and start service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable gunicorn-chm.service
sudo systemctl start gunicorn-chm.service
sudo systemctl status gunicorn-chm.service
```

## Nginx Configuration (Optional)

If using Nginx as reverse proxy:

```bash
sudo nano /etc/nginx/sites-available/chm
```

Add:

```nginx
server {
    listen 80;
    server_name 45.8.225.73;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /var/www/chm/staticfiles/;
    }

    location /media/ {
        alias /var/www/chm/media/;
    }
}
```

Enable site:

```bash
sudo ln -s /etc/nginx/sites-available/chm /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## Troubleshooting

### Check Gunicorn logs:
```bash
sudo journalctl -u gunicorn-chm.service -f
```

### Check if service is running:
```bash
sudo systemctl status gunicorn-chm.service
```

### Restart service:
```bash
sudo systemctl restart gunicorn-chm.service
```

### Check if port 8000 is in use:
```bash
sudo lsof -i :8000
```

### Test Gunicorn manually:
```bash
cd /var/www/chm
source venv/bin/activate
gunicorn --bind 0.0.0.0:8000 hms.wsgi:application
```

## Quick Update Workflow

After making changes locally:

1. **On Local (Windows):**
   ```powershell
   cd C:\Users\user\chm
   git add .
   git commit -m "Your changes"
   git push origin main
   ```

2. **On VPS:**
   ```bash
   cd /var/www/chm
   bash deploy.sh
   ```

That's it! Your changes are live.







