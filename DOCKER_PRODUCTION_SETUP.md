# 🐳 Docker Production Setup Guide

## Quick Start

### 1. Copy Files to Docker Server

Copy your entire project folder to your Docker server:

**From Windows (using PowerShell or CMD):**
```powershell
# Using SCP (if you have OpenSSH installed)
scp -r D:\chm user@your-docker-server:/path/to/destination

# Or use WinSCP, FileZilla, or any SFTP client
```

**Or use Git:**
```bash
# On your Docker server
git clone <your-repo-url>
cd chm
```

### 2. On Docker Server - Start Everything

```bash
# Navigate to project directory
cd /path/to/chm

# Make sure Docker and Docker Compose are installed
docker --version
docker-compose --version

# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### 3. Run Migrations

```bash
# Run database migrations
docker-compose exec web python manage.py migrate

# Create superuser (optional)
docker-compose exec web python manage.py createsuperuser

# Collect static files (if needed)
docker-compose exec web python manage.py collectstatic --noinput
```

### 4. Access Your Application

- **Web Application**: http://your-server-ip:8000
- **MinIO Console**: http://your-server-ip:9001
  - Username: `minioadmin`
  - Password: `minioadmin123`

---

## Configuration

### Environment Variables (.env file)

Your `.env` file should exist. Docker will automatically use it, but the database connection is overridden in `docker-compose.yml` to use Docker's internal network.

**Important**: The `.env` file is used for other settings (SECRET_KEY, DEBUG, etc.), but `DATABASE_URL` and `REDIS_URL` are automatically set by Docker Compose.

### Default Docker Configuration

- **PostgreSQL**: 
  - Host: `db` (internal Docker network)
  - Port: `5432`
  - Database: `hms_db`
  - User: `hms_user`
  - Password: `hms_password`

- **Redis**:
  - Host: `redis` (internal Docker network)
  - Port: `6379`

- **Web Application**:
  - Port: `8000` (exposed to host)

---

## Services Included

1. **db** - PostgreSQL 15 database
2. **redis** - Redis cache
3. **web** - Django application (Gunicorn)
4. **celery** - Celery worker for background tasks
5. **celery-beat** - Celery beat scheduler
6. **minio** - MinIO object storage

---

## Common Commands

### Start Services
```bash
docker-compose up -d
```

### Stop Services
```bash
docker-compose down
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f web
docker-compose logs -f db
```

### Restart Services
```bash
docker-compose restart
docker-compose restart web  # Restart specific service
```

### Execute Commands in Container
```bash
# Django shell
docker-compose exec web python manage.py shell

# Database shell
docker-compose exec web python manage.py dbshell

# Run management command
docker-compose exec web python manage.py <command>
```

### Access Database Directly
```bash
# Connect to PostgreSQL
docker-compose exec db psql -U hms_user -d hms_db
```

### Backup Database
```bash
# Create backup
docker-compose exec db pg_dump -U hms_user hms_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore backup
docker-compose exec -T db psql -U hms_user hms_db < backup_file.sql
```

---

## Production Considerations

### 1. Update .env for Production

Before deploying to production, update your `.env` file:

```bash
# Security
SECRET_KEY=your-very-secure-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,your-server-ip

# Database (automatically set by Docker, but keep for reference)
DATABASE_URL=postgresql://hms_user:hms_password@db:5432/hms_db

# Redis (automatically set by Docker)
REDIS_URL=redis://redis:6379/0

# Other settings...
```

### 2. Use Docker Volumes for Persistence

Your `docker-compose.yml` already uses named volumes:
- `postgres_data` - Database data
- `redis_data` - Redis data
- `minio_data` - MinIO data

These persist even if containers are removed.

### 3. Network Security

- Only expose port 8000 to the internet (or use a reverse proxy)
- Consider using a reverse proxy (Nginx/Traefik) in front
- Use firewall rules to restrict access

### 4. SSL/HTTPS

For production, set up SSL:
- Use Nginx as reverse proxy with Let's Encrypt
- Or use Traefik with automatic SSL
- Or use a cloud load balancer (AWS ALB, Cloudflare, etc.)

### 5. Monitoring

Monitor your containers:
```bash
# Resource usage
docker stats

# Container health
docker-compose ps
```

---

## Troubleshooting

### Database Connection Issues

If you see database connection errors:

1. Check if database is running:
   ```bash
   docker-compose ps db
   ```

2. Check database logs:
   ```bash
   docker-compose logs db
   ```

3. Verify database is ready:
   ```bash
   docker-compose exec db pg_isready -U hms_user
   ```

### Application Not Starting

1. Check application logs:
   ```bash
   docker-compose logs web
   ```

2. Check if migrations are needed:
   ```bash
   docker-compose exec web python manage.py migrate
   ```

3. Rebuild containers:
   ```bash
   docker-compose build --no-cache
   docker-compose up -d
   ```

### Port Already in Use

If port 8000 is already in use:

1. Change port in `docker-compose.yml`:
   ```yaml
   ports:
     - "8080:8000"  # Change 8080 to any available port
   ```

2. Restart:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

### Clear Everything and Start Fresh

```bash
# Stop and remove containers, networks, and volumes
docker-compose down -v

# Rebuild and start
docker-compose build --no-cache
docker-compose up -d
```

---

## Next Steps

1. ✅ Copy files to Docker server
2. ✅ Start services: `docker-compose up -d`
3. ✅ Run migrations: `docker-compose exec web python manage.py migrate`
4. ✅ Create superuser: `docker-compose exec web python manage.py createsuperuser`
5. ✅ Access application at http://your-server-ip:8000
6. ⚠️ Set up reverse proxy (Nginx) for production
7. ⚠️ Configure SSL/HTTPS
8. ⚠️ Set up monitoring and backups

---

## Quick Reference

| Task | Command |
|------|---------|
| Start all services | `docker-compose up -d` |
| Stop all services | `docker-compose down` |
| View logs | `docker-compose logs -f` |
| Restart service | `docker-compose restart web` |
| Run migrations | `docker-compose exec web python manage.py migrate` |
| Create superuser | `docker-compose exec web python manage.py createsuperuser` |
| Django shell | `docker-compose exec web python manage.py shell` |
| Database backup | `docker-compose exec db pg_dump -U hms_user hms_db > backup.sql` |
| Rebuild containers | `docker-compose build --no-cache` |

---

## Support

If you encounter issues:
1. Check logs: `docker-compose logs`
2. Verify all services are running: `docker-compose ps`
3. Check Docker resources: `docker stats`
4. Review this guide's troubleshooting section



