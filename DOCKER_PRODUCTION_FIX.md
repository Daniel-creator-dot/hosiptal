# Docker Production Fix - Complete Guide

## ✅ All Fixes Applied

This document summarizes all the fixes applied to make Docker work independently at production level with automatic restarts and data persistence.

## 🔧 Changes Made

### 1. **Restart Policies Added**
All services now have `restart: unless-stopped` policy:
- ✅ `db` (PostgreSQL) - Auto-restarts on failure
- ✅ `db_2` (MySQL) - Auto-restarts on failure  
- ✅ `redis` - Auto-restarts on failure
- ✅ `web` (Django/Gunicorn) - Auto-restarts on failure
- ✅ `celery` - Auto-restarts on failure
- ✅ `celery-beat` - Auto-restarts on failure
- ✅ `minio` - Auto-restarts on failure

### 2. **Improved Health Checks**
- ✅ All services have proper health checks with appropriate intervals
- ✅ Health checks wait for services to be ready before marking as healthy
- ✅ Increased retry counts for better reliability
- ✅ Proper start periods to allow services to initialize

### 3. **Database Persistence**
- ✅ All database volumes are properly configured with `driver: local`
- ✅ PostgreSQL data persists in `postgres_data` volume
- ✅ MySQL data persists in `mysql_import_data` volume
- ✅ Redis data persists in `redis_data` volume
- ✅ MinIO data persists in `minio_data` volume
- ✅ Celery beat schedule persists in `celerybeat_data` volume

### 4. **Service Dependencies**
- ✅ All services wait for database to be healthy before starting
- ✅ Web, Celery, and Celery-Beat wait for both PostgreSQL and Redis
- ✅ Proper wait loops in startup commands to ensure database is ready

### 5. **Container Names**
- ✅ All containers have explicit names for easier management:
  - `hms_postgres`
  - `hms_mysql`
  - `hms_redis`
  - `hms_web`
  - `hms_celery`
  - `hms_celery_beat`
  - `hms_minio`

### 6. **Improved Startup Commands**
- ✅ Web service waits for database before running migrations
- ✅ All services run migrations automatically on startup
- ✅ Static files collected on every startup to ensure they're up-to-date
- ✅ Proper error handling in startup scripts

## 📋 Required .env Configuration

Your `.env` file **MUST** contain these variables:

```bash
# Required: Database URL (for local development)
# Docker will automatically override this to use 'db' hostname
DATABASE_URL=postgresql://hms_user:hms_password@localhost:5432/hms_db

# Required: Django Secret Key
SECRET_KEY=your-secret-key-here-generate-a-new-one

# Required: Debug mode (False for production)
DEBUG=False

# Required: Allowed hosts
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

# Required: Redis URL (for local development)
# Docker will automatically override this to use 'redis' hostname
REDIS_URL=redis://localhost:6379/0
```

**Note**: Docker Compose automatically overrides `DATABASE_URL` and `REDIS_URL` to use service names (`db` and `redis`) instead of `localhost`.

## 🚀 Usage

### Start All Services
```bash
docker-compose up -d
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f web
docker-compose logs -f db
```

### Stop Services
```bash
docker-compose down
```

### Restart Services
```bash
docker-compose restart
```

### Restart Specific Service
```bash
docker-compose restart web
```

### View Service Status
```bash
docker-compose ps
```

### Access Services
- **Web Application**: http://localhost:8000
- **PostgreSQL**: localhost:5432
- **MySQL**: localhost:3306
- **Redis**: localhost:6379
- **MinIO Console**: http://localhost:9001
- **MinIO API**: http://localhost:9000

## 🔄 Automatic Restart Behavior

All services are configured with `restart: unless-stopped`, which means:

1. ✅ **On Docker Desktop restart**: All services automatically start
2. ✅ **On container crash**: Container automatically restarts
3. ✅ **On system reboot**: All services automatically start (if Docker Desktop is set to start on boot)
4. ✅ **On manual stop**: Services stay stopped until manually started

## 💾 Data Persistence

All data is stored in Docker volumes and persists across restarts:

- **PostgreSQL Data**: `postgres_data` volume
- **MySQL Data**: `mysql_import_data` volume
- **Redis Data**: `redis_data` volume
- **MinIO Data**: `minio_data` volume
- **Celery Beat Schedule**: `celerybeat_data` volume

To backup volumes:
```bash
docker run --rm -v postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz /data
```

To restore volumes:
```bash
docker run --rm -v postgres_data:/data -v $(pwd):/backup alpine tar xzf /backup/postgres_backup.tar.gz -C /
```

## 🏥 Health Checks

All services have health checks configured:

- **PostgreSQL**: Checks if database is ready to accept connections
- **Redis**: Checks if Redis is responding to ping
- **Web**: Checks if `/health/` endpoint responds (Django health check)
- **Celery**: Checks if Celery worker is responding
- **Celery Beat**: Checks if Celery beat process is running
- **MinIO**: Checks if MinIO health endpoint responds

View health status:
```bash
docker-compose ps
```

## 🐛 Troubleshooting

### Services Won't Start

1. **Check logs**:
   ```bash
   docker-compose logs
   ```

2. **Verify .env file**:
   ```bash
   # Windows
   docker-startup-check.bat
   
   # Linux/Mac
   bash docker-startup-check.sh
   ```

3. **Check database connection**:
   ```bash
   docker-compose exec db pg_isready -U hms_user -d hms_db
   ```

4. **Check Redis connection**:
   ```bash
   docker-compose exec redis redis-cli ping
   ```

### Database Connection Errors

If you see database connection errors:

1. Ensure PostgreSQL is healthy:
   ```bash
   docker-compose ps db
   ```

2. Check database logs:
   ```bash
   docker-compose logs db
   ```

3. Verify DATABASE_URL in docker-compose.yml (should use 'db' hostname)

### Static Files Not Loading

Static files are collected on every startup. If they're not loading:

1. Check web service logs:
   ```bash
   docker-compose logs web | grep collectstatic
   ```

2. Manually collect static files:
   ```bash
   docker-compose exec web python manage.py collectstatic --noinput
   ```

### Migrations Not Running

Migrations run automatically on startup. If they're not running:

1. Check web service logs:
   ```bash
   docker-compose logs web | grep migrate
   ```

2. Manually run migrations:
   ```bash
   docker-compose exec web python manage.py migrate
   ```

## ✅ Verification Checklist

Before considering the setup complete, verify:

- [ ] All services start successfully: `docker-compose ps`
- [ ] Web application is accessible: http://localhost:8000
- [ ] Health check endpoint works: http://localhost:8000/health/
- [ ] Database connection works (check web logs)
- [ ] Redis connection works (check web logs)
- [ ] Services restart automatically after `docker-compose restart`
- [ ] Data persists after `docker-compose down && docker-compose up -d`

## 📝 Notes

- All services are configured for **production-level** operation
- Services automatically handle migrations and static file collection on startup
- Database and all data persist across restarts
- Health checks ensure services are ready before dependent services start
- All containers have explicit names for easier management

## 🎯 Next Steps

1. **Verify .env file** has all required variables (see above)
2. **Start services**: `docker-compose up -d`
3. **Check status**: `docker-compose ps`
4. **View logs**: `docker-compose logs -f`
5. **Access application**: http://localhost:8000

---

**All fixes have been applied. Your Docker setup is now production-ready and will work independently on restart!** 🎉














