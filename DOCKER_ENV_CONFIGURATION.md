# Docker Environment Configuration for Live Server Deployment

This document contains the complete environment configuration needed to deploy the HMS application on a live server.

---

## 1. DJANGO_SETTINGS_MODULE

**Value:** `hms.settings`

This is set in:
- `Dockerfile` (line 41): `ENV DJANGO_SETTINGS_MODULE=hms.settings`
- `docker-compose.yml`: Inherited from Dockerfile
- All Django management commands use this by default

**No need to set this in .env file** - it's already configured in the Dockerfile.

---

## 2. Database Configuration (Docker)

### Database Credentials Used in Docker:

From `docker-compose.yml`:

- **Database Name:** `hms_db`
- **Database User:** `hms_user`
- **Database Password:** `hms_password`
- **Database Host:** `db` (Docker service name)
- **Database Port:** `5432`
- **Database Type:** PostgreSQL 15

### DATABASE_URL Format:

**Inside Docker (for web, celery, celery-beat services):**
```
postgresql://hms_user:hms_password@db:5432/hms_db
```

**For External Access (from host machine or remote):**
```
postgresql://hms_user:hms_password@localhost:5432/hms_db
```
or
```
postgresql://hms_user:hms_password@YOUR_SERVER_IP:5432/hms_db
```

---

## 3. Complete .env File Structure

Create a `.env` file in the project root with the following structure:

```bash
# ====================================
# DJANGO CORE SETTINGS
# ====================================
# Note: DJANGO_SETTINGS_MODULE is set in Dockerfile, no need to set here

# Security
SECRET_KEY=YOUR_SUPER_SECRET_KEY_HERE_CHANGE_THIS_IN_PRODUCTION
DEBUG=False

# Domain Configuration (REQUIRED FOR PRODUCTION)
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
SITE_URL=https://yourdomain.com

# CSRF Configuration (auto-generated from ALLOWED_HOSTS in production, but can override)
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# ====================================
# DATABASE CONFIGURATION
# ====================================
# For Docker: Use 'db' as hostname (Docker service name)
# For External: Use 'localhost' or your server IP
# docker-compose.yml automatically overrides this to use 'db' hostname

# Docker Internal (automatically set by docker-compose.yml)
DATABASE_URL=postgresql://hms_user:hms_password@db:5432/hms_db

# For External Access (if connecting from outside Docker)
# DATABASE_URL=postgresql://hms_user:hms_password@localhost:5432/hms_db

# Database Performance Settings
DATABASE_CONN_MAX_AGE=600
DATABASE_CONN_HEALTH_CHECKS=True
DATABASE_TIMEOUT=10
DATABASE_SSL_MODE=prefer

# ====================================
# REDIS CONFIGURATION
# ====================================
# For Docker: Use 'redis' as hostname (Docker service name)
# docker-compose.yml automatically overrides this to use 'redis' hostname

# Docker Internal (automatically set by docker-compose.yml)
REDIS_URL=redis://redis:6379/0

# For External Access (if connecting from outside Docker)
# REDIS_URL=redis://localhost:6379/0

USE_REDIS_CACHE=True

# ====================================
# EMAIL CONFIGURATION (REQUIRED)
# ====================================
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password-here
DEFAULT_FROM_EMAIL=noreply@yourdomain.com

# ====================================
# SMS CONFIGURATION (SMS Notify GH)
# ====================================
SMS_API_KEY=your-sms-api-key-here
SMS_SENDER_ID=PrimeCare
SMS_API_URL=https://sms.smsnotifygh.com/smsapi

# ====================================
# HOSPITAL BRANDING
# ====================================
HOSPITAL_NAME=PrimeCare Hospital
HOSPITAL_LOGO_URL=https://yourdomain.com/static/logo.png

# ====================================
# SECURITY SETTINGS
# ====================================
SECURE_SSL_REDIRECT=True
SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https

# ====================================
# CORS SETTINGS
# ====================================
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# ====================================
# ADMIN NOTIFICATIONS
# ====================================
# Format: Name:email,Name2:email2
ADMINS=Admin Name:admin@yourdomain.com

# ====================================
# WHATSAPP CONFIGURATION (Optional)
# ====================================
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886

# Meta WhatsApp Business API (Alternative)
USE_META_WHATSAPP_API=False
META_WHATSAPP_ACCESS_TOKEN=
META_WHATSAPP_PHONE_NUMBER_ID=

# ====================================
# ERROR MONITORING (Optional - Sentry)
# ====================================
SENTRY_DSN=

# ====================================
# CLOUD STORAGE (Optional - AWS S3)
# ====================================
# AWS_ACCESS_KEY_ID=
# AWS_SECRET_ACCESS_KEY=
# AWS_STORAGE_BUCKET_NAME=
# AWS_S3_REGION_NAME=us-east-1
```

---

## 4. Docker Compose Environment Overrides

The `docker-compose.yml` file automatically overrides these environment variables for Docker services:

### For `web`, `celery`, and `celery-beat` services:

```yaml
environment:
  # Database URL - uses 'db' as hostname (Docker service name)
  - DATABASE_URL=postgresql://hms_user:hms_password@db:5432/hms_db
  
  # Redis URL - uses 'redis' as hostname (Docker service name)
  - REDIS_URL=redis://redis:6379/0
```

**Important:** These overrides happen automatically in Docker. You don't need to set them in `.env` file for Docker deployment, but they're shown here for reference.

---

## 5. Database Connection Details Summary

### For Server Company to Mount Database:

| Setting | Value |
|---------|-------|
| **Database Type** | PostgreSQL 15 |
| **Database Name** | `hms_db` |
| **Database User** | `hms_user` |
| **Database Password** | `hms_password` |
| **Database Port** | `5432` |
| **Connection String (Docker)** | `postgresql://hms_user:hms_password@db:5432/hms_db` |
| **Connection String (External)** | `postgresql://hms_user:hms_password@localhost:5432/hms_db` |

### PostgreSQL Container Configuration:

From `docker-compose.yml`:
- **Image:** `postgres:15-alpine`
- **Volume:** `postgres_data:/var/lib/postgresql/data`
- **Port Mapping:** `5432:5432` (host:container)
- **Health Check:** `pg_isready -U hms_user -d hms_db`

---

## 6. Important Notes for Server Deployment

### A. Environment Variables Priority:

1. **Docker Compose environment section** (highest priority)
2. **.env file** (loaded via `env_file: - .env`)
3. **Dockerfile ENV** (defaults)

### B. Database Connection:

- **Inside Docker:** Services connect using `db:5432` (Docker service name)
- **From Host:** Connect using `localhost:5432` or server IP
- **From Remote:** Connect using `SERVER_IP:5432`

### C. Security Recommendations:

1. **Change default passwords** before production:
   - `hms_password` → Use strong password
   - `SECRET_KEY` → Generate new secret key
   - `EMAIL_HOST_PASSWORD` → Use app-specific password

2. **Generate SECRET_KEY:**
   ```bash
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```

3. **Set DEBUG=False** in production

4. **Configure ALLOWED_HOSTS** with your actual domain(s)

### D. Required Environment Variables for Production:

**Minimum Required:**
- `SECRET_KEY` (must be set)
- `DEBUG=False`
- `ALLOWED_HOSTS` (your domain)
- `SITE_URL` (your domain URL)
- `DATABASE_URL` (auto-set by docker-compose.yml)
- `EMAIL_*` settings (for email login to work)

---

## 7. Quick Start for Server Company

### Step 1: Create .env file
```bash
cp env.example .env
# Edit .env with production values
```

### Step 2: Update these critical values:
```bash
SECRET_KEY=<generate-new-secret-key>
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
SITE_URL=https://yourdomain.com
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

### Step 3: Database is already configured in docker-compose.yml:
- User: `hms_user`
- Password: `hms_password`
- Database: `hms_db`
- Host: `db` (inside Docker)

### Step 4: Start services:
```bash
docker-compose up -d
```

---

## 8. Verification Commands

### Check Database Connection:
```bash
docker-compose exec web python manage.py dbshell
```

### Check Environment Variables:
```bash
docker-compose exec web env | grep DJANGO
docker-compose exec web env | grep DATABASE
```

### Check Database Credentials:
```bash
docker-compose exec db psql -U hms_user -d hms_db -c "SELECT version();"
```

---

## 9. Contact Information

For questions about this configuration, refer to:
- `LIVE_SERVER_DEPLOYMENT_FIX.md` - Complete deployment guide
- `docker-compose.yml` - Docker service configuration
- `Dockerfile` - Container build configuration

---

**Last Updated:** $(date)
**Version:** 1.0.0




