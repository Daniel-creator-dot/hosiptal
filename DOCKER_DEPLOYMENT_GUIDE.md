# 🐳 Docker Deployment Guide

Complete guide to build, push, and run your HMS application using Docker.

---

## 📋 Prerequisites

1. **Docker Desktop** installed and running
   - Download from: https://www.docker.com/products/docker-desktop
   - Make sure it's running (you'll see the Docker icon in system tray)

2. **Docker Hub Account** (for pushing images)
   - Sign up at: https://hub.docker.com
   - It's free!

---

## 🚀 Quick Start

### Option 1: Build and Push to Docker Hub (Recommended)

1. **Build and Push**:
   ```bash
   docker-build-push.bat
   ```
   - Enter your Docker Hub username when prompted
   - Enter your Docker Hub password when prompted
   - Wait for build and push to complete (5-10 minutes)

2. **Run from Docker Hub**:
   ```bash
   docker-run.bat
   ```
   - Enter your Docker Hub username when prompted
   - Container will start automatically

### Option 2: Build and Run Locally

1. **Build locally**:
   ```bash
   docker build -t hms:latest .
   ```

2. **Run with docker-compose** (includes database, redis, etc.):
   ```bash
   docker-compose up -d
   ```

3. **Or run standalone**:
   ```bash
   docker run -d --name hms-container -p 8000:8000 hms:latest
   ```

---

## 📖 Detailed Instructions

### Step 1: Build Docker Image

#### Using the Script (Easiest)
```bash
docker-build-push.bat
```

#### Manual Build
```bash
# Build the image
docker build -t your-username/hms:latest .

# Tag it (optional, for versioning)
docker tag your-username/hms:latest your-username/hms:v1.0.0
```

### Step 2: Push to Docker Hub

#### Using the Script
The `docker-build-push.bat` script will automatically push after building.

#### Manual Push
```bash
# Login to Docker Hub
docker login

# Push the image
docker push your-username/hms:latest

# Push tagged version (if you created one)
docker push your-username/hms:v1.0.0
```

### Step 3: Run the Container

#### Option A: Using docker-compose (Full Stack)
This starts everything: web app, database, redis, celery, etc.

```bash
# Make sure you have a .env file
# Copy compose.env to .env and update values if needed

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f web

# Stop all services
docker-compose down
```

#### Option B: Using docker-run.bat Script
```bash
docker-run.bat
```

#### Option C: Manual Docker Run
```bash
# Pull from Docker Hub (if not local)
docker pull your-username/hms:latest

# Run the container
docker run -d \
  --name hms-container \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql://hms_user:hms_password@host.docker.internal:5432/hms_db \
  -e REDIS_URL=redis://host.docker.internal:6379/0 \
  -e SECRET_KEY=your-secret-key-here \
  -e DEBUG=True \
  -e ALLOWED_HOSTS=* \
  your-username/hms:latest
```

---

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=*
DATABASE_URL=postgresql://hms_user:hms_password@db:5432/hms_db
REDIS_URL=redis://redis:6379/0
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
SMS_API_KEY=your-sms-api-key
```

### For Docker Compose
The `docker-compose.yml` automatically uses:
- Database: `postgresql://hms_user:hms_password@db:5432/hms_db`
- Redis: `redis://redis:6379/0`

### For Standalone Container
If running just the web container, you need:
- External PostgreSQL (or use `host.docker.internal:5432` for local PostgreSQL)
- External Redis (or use `host.docker.internal:6379` for local Redis)

---

## 🎯 Common Commands

### View Logs
```bash
# Docker Compose
docker-compose logs -f web

# Standalone container
docker logs -f hms-container
```

### Stop Container
```bash
# Docker Compose
docker-compose down

# Standalone
docker stop hms-container
docker rm hms-container
```

### Restart Container
```bash
# Docker Compose
docker-compose restart web

# Standalone
docker restart hms-container
```

### Access Container Shell
```bash
# Docker Compose
docker-compose exec web bash

# Standalone
docker exec -it hms-container bash
```

### Run Django Commands
```bash
# Docker Compose
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser

# Standalone
docker exec hms-container python manage.py migrate
docker exec -it hms-container python manage.py createsuperuser
```

---

## 🐛 Troubleshooting

### Build Fails

**Error: "Cannot connect to Docker daemon"**
- Make sure Docker Desktop is running
- Restart Docker Desktop

**Error: "No space left on device"**
- Clean up Docker: `docker system prune -a`
- Free up disk space

### Container Won't Start

**Error: "Port already in use"**
- Stop the service using port 8000
- Or change the port: `-p 8001:8000`

**Error: "Cannot connect to database"**
- Make sure PostgreSQL is running
- Check DATABASE_URL environment variable
- For docker-compose, wait for database to be healthy

### Application Not Accessible

**Can't access http://localhost:8000**
- Check if container is running: `docker ps`
- Check logs: `docker logs hms-container`
- Verify port mapping: `docker port hms-container`

### Database Connection Issues

**For docker-compose:**
- Wait for database to be healthy (check with `docker-compose ps`)
- Database should show as "healthy" before web starts

**For standalone container:**
- Make sure PostgreSQL is accessible from container
- Use `host.docker.internal` for local PostgreSQL
- Or use full Docker network setup

---

## 📦 What Gets Built

The Docker image includes:
- ✅ Python 3.12
- ✅ All Python dependencies from `requirements.txt`
- ✅ PostgreSQL client libraries
- ✅ All application code
- ✅ Static files collected
- ✅ Gunicorn web server (production-ready)

---

## 🌐 Accessing the Application

Once running:
- **Web Interface**: http://localhost:8000
- **Admin Panel**: http://localhost:8000/admin
- **Health Check**: http://localhost:8000/health/
- **API**: http://localhost:8000/api/

---

## 🔐 Security Notes

1. **Never commit `.env` file** - it contains secrets
2. **Change default passwords** in production
3. **Use strong SECRET_KEY** in production
4. **Set DEBUG=False** in production
5. **Configure ALLOWED_HOSTS** properly

---

## 📚 Next Steps

After successful deployment:
1. Create superuser: `docker-compose exec web python manage.py createsuperuser`
2. Run migrations: `docker-compose exec web python manage.py migrate`
3. Initialize system: `docker-compose exec web python manage.py init_hms`
4. Access admin panel and configure your hospital

---

## 🎉 Success!

Your HMS is now running in Docker! 🐳

For production deployment, consider:
- Using Docker Hub or private registry
- Setting up proper environment variables
- Configuring SSL/HTTPS
- Setting up monitoring and backups
- Using orchestration (Docker Swarm, Kubernetes)

---

**Questions?** Check the logs or Docker documentation: https://docs.docker.com

