# Production Deployment Checklist for HMS

## Pre-Deployment Checklist

### 1. Environment Configuration
- [ ] Copy `.env.example` to `.env` and fill in production values
- [ ] Generate a strong SECRET_KEY (use `python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'`)
- [ ] Set `DEBUG=False`
- [ ] Configure `ALLOWED_HOSTS` with your domain(s)
- [ ] Set up production database (PostgreSQL recommended)
- [ ] Configure Redis for caching and Celery
- [ ] Set up email server (SMTP)
- [ ] Configure SMS API credentials
- [ ] Set `SITE_URL` to your production domain

### 2. Database Setup
```bash
# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput
```

### 3. Security Hardening
- [ ] Ensure HTTPS is enabled (SSL certificate installed)
- [ ] Verify `SECURE_SSL_REDIRECT=True`
- [ ] Check HSTS headers are enabled
- [ ] Verify CSRF and session cookies are secure
- [ ] Review and configure CSP headers
- [ ] Set up firewall rules
- [ ] Configure rate limiting
- [ ] Review file upload restrictions
- [ ] Set up database backups
- [ ] Configure log rotation

### 4. Performance Optimization
- [ ] Enable Redis caching
- [ ] Configure database connection pooling
- [ ] Set up CDN for static files (optional)
- [ ] Enable Gzip compression (handled by WhiteNoise)
- [ ] Configure query optimization settings
- [ ] Set up database indexes
- [ ] Enable template caching
- [ ] Configure Celery for background tasks

### 5. Monitoring & Logging
- [ ] Set up Sentry for error tracking (optional)
- [ ] Configure log aggregation
- [ ] Set up uptime monitoring
- [ ] Configure health checks
- [ ] Set up Prometheus metrics (optional)
- [ ] Configure admin email notifications for errors
- [ ] Set up database monitoring

### 6. Backup Strategy
- [ ] Configure automated database backups
- [ ] Set up media files backup
- [ ] Test backup restoration process
- [ ] Document backup procedures
- [ ] Set up off-site backup storage

### 7. Application Server
Choose one of the following:

#### Option A: Gunicorn (Recommended)
```bash
# Install
pip install gunicorn

# Run
gunicorn hms.wsgi:application --bind 0.0.0.0:8000 --workers 4 --timeout 120
```

#### Option B: uWSGI
```bash
# Install
pip install uwsgi

# Run
uwsgi --http :8000 --module hms.wsgi --master --processes 4
```

### 8. Web Server Configuration

#### Nginx Configuration (Recommended)
```nginx
upstream django {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    # SSL Configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    client_max_body_size 20M;

    location /static/ {
        alias /path/to/your/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /path/to/your/media/;
    }

    location / {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 120s;
        proxy_read_timeout 120s;
    }
}
```

### 9. Process Management

#### Systemd Service for Gunicorn
Create `/etc/systemd/system/hms.service`:
```ini
[Unit]
Description=HMS Gunicorn Daemon
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/hms
ExecStart=/path/to/venv/bin/gunicorn \
          --workers 4 \
          --bind unix:/path/to/hms.sock \
          --timeout 120 \
          hms.wsgi:application

[Install]
WantedBy=multi-user.target
```

#### Systemd Service for Celery Worker
Create `/etc/systemd/system/celery-worker.service`:
```ini
[Unit]
Description=HMS Celery Worker
After=network.target

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/path/to/hms
ExecStart=/path/to/venv/bin/celery -A hms worker --loglevel=info

[Install]
WantedBy=multi-user.target
```

#### Systemd Service for Celery Beat
Create `/etc/systemd/system/celery-beat.service`:
```ini
[Unit]
Description=HMS Celery Beat
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/path/to/hms
ExecStart=/path/to/venv/bin/celery -A hms beat --loglevel=info

[Install]
WantedBy=multi-user.target
```

Enable and start services:
```bash
sudo systemctl enable hms
sudo systemctl enable celery-worker
sudo systemctl enable celery-beat
sudo systemctl start hms
sudo systemctl start celery-worker
sudo systemctl start celery-beat
```

### 10. Post-Deployment Verification
- [ ] Test homepage loads correctly
- [ ] Verify HTTPS redirect works
- [ ] Test user login/logout
- [ ] Verify static files load correctly
- [ ] Test patient registration
- [ ] Verify appointment scheduling
- [ ] Test billing functionality
- [ ] Check ambulance tracking
- [ ] Verify SMS notifications work
- [ ] Test email sending
- [ ] Check background tasks (Celery)
- [ ] Review error logs
- [ ] Test backup and restore

### 11. Maintenance Tasks

#### Daily
- Monitor error logs
- Check system resources
- Review backup status

#### Weekly
- Review performance metrics
- Check disk space
- Update dependencies (if needed)

#### Monthly
- Security audit
- Performance optimization review
- Database optimization
- Test backup restoration

## Production Deployment Commands

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Install production dependencies
pip install -r requirements.txt

# 3. Set environment variables
export DJANGO_SETTINGS_MODULE=hms.settings
export DEBUG=False

# 4. Run migrations
python manage.py migrate --no-input

# 5. Collect static files
python manage.py collectstatic --no-input

# 6. Create cache table (if using database cache)
python manage.py createcachetable

# 7. Compile translations (if using i18n)
python manage.py compilemessages

# 8. Check deployment
python manage.py check --deploy

# 9. Start services
sudo systemctl restart hms
sudo systemctl restart celery-worker
sudo systemctl restart celery-beat
sudo systemctl restart nginx
```

## Rollback Procedure

If deployment fails:

```bash
# 1. Stop services
sudo systemctl stop hms

# 2. Restore database from backup
pg_restore -d hms_db backup.sql

# 3. Checkout previous version
git checkout <previous-commit-hash>

# 4. Run migrations (if needed)
python manage.py migrate

# 5. Collect static files
python manage.py collectstatic --no-input

# 6. Restart services
sudo systemctl start hms
```

## Performance Tuning

### Database Optimization
```sql
-- Create indexes for frequently queried fields
CREATE INDEX idx_patient_mrn ON hospital_patient(mrn);
CREATE INDEX idx_encounter_date ON hospital_encounter(encounter_date);
CREATE INDEX idx_appointment_datetime ON hospital_appointment(appointment_datetime);

-- Analyze tables
ANALYZE;
```

### Redis Configuration
Edit `/etc/redis/redis.conf`:
```
maxmemory 256mb
maxmemory-policy allkeys-lru
```

### Gunicorn Workers
Rule of thumb: `workers = (2 x $num_cores) + 1`

For 2 CPU cores: 5 workers
For 4 CPU cores: 9 workers

## Troubleshooting

### 502 Bad Gateway
- Check if Gunicorn is running: `sudo systemctl status hms`
- Check Gunicorn logs: `sudo journalctl -u hms -n 50`
- Verify socket file permissions

### Static Files Not Loading
- Run `python manage.py collectstatic --no-input`
- Check Nginx configuration
- Verify file permissions

### Database Connection Issues
- Check PostgreSQL is running
- Verify DATABASE_URL in .env
- Check database user permissions
- Review pg_hba.conf for authentication

### High Memory Usage
- Reduce number of Gunicorn workers
- Enable database connection pooling
- Configure Redis maxmemory
- Review Celery worker concurrency

## Security Incident Response

1. **Identify the threat**
2. **Isolate affected systems**
3. **Review logs for suspicious activity**
4. **Change compromised credentials**
5. **Apply security patches**
6. **Restore from clean backup if necessary**
7. **Document the incident**
8. **Review and update security procedures**

## Support & Maintenance

For production support:
- Monitor error logs daily
- Set up alerts for critical errors
- Regular security updates
- Performance monitoring
- Database maintenance

## Additional Resources

- [Django Deployment Checklist](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/)
- [Gunicorn Documentation](https://docs.gunicorn.org/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [PostgreSQL Performance](https://www.postgresql.org/docs/current/performance-tips.html)
















