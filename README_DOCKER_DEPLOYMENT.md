# 🐳 Docker Production Deployment - README

## 📦 What's Included

This project is ready for Docker production deployment. All necessary files are configured.

## 🚀 Quick Start (3 Steps)

### 1. Copy Files to Docker Server
Copy your entire project folder to your Docker server.

### 2. On Docker Server - Start Services
```bash
cd /path/to/chm
docker-compose up -d
```

### 3. Run Migrations
```bash
docker-compose exec web python manage.py migrate
```

**That's it!** Your application should be running at `http://your-server-ip:8000`

---

## 📚 Documentation Files

1. **DOCKER_PRODUCTION_SETUP.md** - Complete deployment guide with all details
2. **DOCKER_QUICK_START.txt** - Quick reference card
3. **DOCKER_DEPLOYMENT_CHECKLIST.md** - Step-by-step checklist
4. **docker-start-production.sh** - Automated setup script (Linux/Mac)
5. **docker-start-production.bat** - File verification script (Windows)

---

## 🎯 What Gets Deployed

Your Docker setup includes:

- ✅ **PostgreSQL 15** - Production database
- ✅ **Redis** - Caching and task queue
- ✅ **Django + Gunicorn** - Web application server
- ✅ **Celery** - Background task processing
- ✅ **Celery Beat** - Scheduled tasks
- ✅ **MinIO** - Object storage

All services are configured and ready to run!

---

## ⚙️ Configuration

### Database
- Automatically configured in Docker
- User: `hms_user`
- Password: `hms_password`
- Database: `hms_db`
- **No manual setup needed!**

### Environment Variables
Your `.env` file is used for:
- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- Other Django settings

Database and Redis URLs are automatically set by Docker Compose.

---

## 🔧 Common Tasks

### Start Services
```bash
docker-compose up -d
```

### View Logs
```bash
docker-compose logs -f
```

### Stop Services
```bash
docker-compose down
```

### Restart a Service
```bash
docker-compose restart web
```

### Run Django Commands
```bash
docker-compose exec web python manage.py <command>
```

### Create Superuser
```bash
docker-compose exec web python manage.py createsuperuser
```

### Backup Database
```bash
docker-compose exec db pg_dump -U hms_user hms_db > backup.sql
```

---

## 📋 Pre-Deployment Checklist

Before deploying, make sure:

- [ ] `.env` file has `DEBUG=False`
- [ ] `.env` file has secure `SECRET_KEY`
- [ ] `.env` file has `ALLOWED_HOSTS` set correctly
- [ ] All code is committed/saved
- [ ] Docker is installed on target server
- [ ] Docker Compose is installed on target server

---

## 🆘 Troubleshooting

### Services Won't Start
```bash
# Check logs
docker-compose logs

# Rebuild containers
docker-compose build --no-cache
docker-compose up -d
```

### Database Connection Errors
```bash
# Check database is running
docker-compose ps db

# Check database logs
docker-compose logs db
```

### Port Already in Use
Edit `docker-compose.yml` and change the port mapping:
```yaml
ports:
  - "8080:8000"  # Change 8080 to available port
```

### Need Fresh Start
```bash
# WARNING: This deletes all data!
docker-compose down -v
docker-compose up -d
```

---

## 📞 Support

For detailed instructions, see:
- **DOCKER_PRODUCTION_SETUP.md** - Full guide
- **DOCKER_QUICK_START.txt** - Quick reference

---

## ✅ You're Ready!

Your project is fully configured for Docker production deployment. Just copy the files and run `docker-compose up -d`!

Good luck with your deployment! 🚀



