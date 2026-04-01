# 🐳 Docker Deployment Checklist

Use this checklist when deploying to Docker production.

## Pre-Deployment

- [ ] All code changes committed
- [ ] `.env` file configured for production
- [ ] `SECRET_KEY` set to secure value
- [ ] `DEBUG=False` for production
- [ ] `ALLOWED_HOSTS` includes your domain/IP
- [ ] Database credentials verified
- [ ] All migrations tested locally

## File Transfer

- [ ] Project folder copied to Docker server
- [ ] All files transferred successfully
- [ ] Permissions set correctly on server
- [ ] `.env` file exists on server

## Docker Setup

- [ ] Docker installed on server
- [ ] Docker Compose installed on server
- [ ] Docker service running
- [ ] Sufficient disk space available
- [ ] Ports 8000, 5432, 6379, 9000, 9001 available

## Deployment Steps

- [ ] Navigated to project directory
- [ ] `docker-compose.yml` verified
- [ ] `Dockerfile` verified
- [ ] `requirements.txt` verified
- [ ] Built Docker images: `docker-compose build`
- [ ] Started containers: `docker-compose up -d`
- [ ] All services running: `docker-compose ps`
- [ ] No errors in logs: `docker-compose logs`

## Database Setup

- [ ] Database container running
- [ ] Migrations executed: `docker-compose exec web python manage.py migrate`
- [ ] No migration errors
- [ ] Superuser created (if needed)
- [ ] Database connection tested

## Application Verification

- [ ] Web application accessible
- [ ] Login page loads
- [ ] Can log in with superuser
- [ ] Static files loading correctly
- [ ] Media files accessible (if applicable)
- [ ] No 500 errors in logs

## Services Verification

- [ ] PostgreSQL database accessible
- [ ] Redis cache working
- [ ] Celery worker running
- [ ] Celery beat scheduler running
- [ ] MinIO accessible (if used)

## Security

- [ ] `DEBUG=False` in production
- [ ] Strong `SECRET_KEY` set
- [ ] Database password secure
- [ ] Firewall rules configured
- [ ] Only necessary ports exposed
- [ ] SSL/HTTPS configured (if applicable)

## Monitoring

- [ ] Logs accessible
- [ ] Health checks working
- [ ] Resource usage monitored
- [ ] Backup strategy in place

## Post-Deployment

- [ ] Application fully functional
- [ ] All features tested
- [ ] Performance acceptable
- [ ] Documentation updated
- [ ] Team notified of deployment

## Rollback Plan

- [ ] Previous version backed up
- [ ] Rollback procedure documented
- [ ] Database backup created
- [ ] Know how to revert if needed

---

## Quick Commands Reference

```bash
# Start everything
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# Restart service
docker-compose restart web

# Stop everything
docker-compose down

# Backup database
docker-compose exec db pg_dump -U hms_user hms_db > backup.sql
```

---

**Date Deployed:** _______________
**Deployed By:** _______________
**Server IP/Domain:** _______________
**Notes:** _______________



