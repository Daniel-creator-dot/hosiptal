# 🐳 Docker Quick Start

**Push to Docker Hub and run your HMS application in 3 simple steps!**

---

## ⚡ Quick Steps

### Step 1: Build and Push to Docker Hub

**Windows:**
```bash
docker-build-push.bat
```

**Linux/Mac:**
```bash
./docker-build-push.sh
```

**What it does:**
- ✅ Checks Docker is running
- ✅ Builds your Docker image
- ✅ Pushes to Docker Hub
- ✅ Makes it available worldwide!

**You'll need:**
- Docker Hub username (sign up at https://hub.docker.com - it's free!)
- Docker Hub password

---

### Step 2: Run from Docker Hub

**Windows:**
```bash
docker-run.bat
```

**Linux/Mac:**
```bash
./docker-run.sh
```

**What it does:**
- ✅ Pulls your image from Docker Hub (or uses local)
- ✅ Starts the container
- ✅ Makes it available at http://localhost:8000

---

### Step 3: Access Your Application

Open your browser:
- 🌐 **Web**: http://localhost:8000
- 🔧 **Admin**: http://localhost:8000/admin
- ❤️ **Health**: http://localhost:8000/health/

---

## 🎯 Alternative: Use Docker Compose (Full Stack)

If you want to run everything (web + database + redis + celery):

```bash
docker-compose up -d
```

This starts:
- ✅ Web application
- ✅ PostgreSQL database
- ✅ Redis cache
- ✅ Celery worker
- ✅ Celery beat
- ✅ MinIO storage

**View logs:**
```bash
docker-compose logs -f web
```

**Stop everything:**
```bash
docker-compose down
```

---

## 📋 Manual Commands

### Build Image
```bash
docker build -t your-username/hms:latest .
```

### Push to Docker Hub
```bash
docker login
docker push your-username/hms:latest
```

### Run Container
```bash
docker run -d \
  --name hms-container \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql://hms_user:hms_password@host.docker.internal:5432/hms_db \
  -e REDIS_URL=redis://host.docker.internal:6379/0 \
  your-username/hms:latest
```

---

## 🔍 Useful Commands

### View Logs
```bash
docker logs -f hms-container
```

### Stop Container
```bash
docker stop hms-container
```

### Remove Container
```bash
docker rm hms-container
```

### Restart Container
```bash
docker restart hms-container
```

### Access Container Shell
```bash
docker exec -it hms-container bash
```

### Run Django Commands
```bash
docker exec hms-container python manage.py migrate
docker exec -it hms-container python manage.py createsuperuser
```

---

## ⚠️ Important Notes

1. **Make sure Docker Desktop is running** before running scripts
2. **For standalone container**, you need PostgreSQL and Redis running separately
3. **For full stack**, use `docker-compose up -d` instead
4. **First time setup**: Run migrations and create superuser after starting

---

## 🆘 Troubleshooting

**Docker not running?**
- Start Docker Desktop
- Wait for it to fully start (green icon)

**Port 8000 already in use?**
- Stop the service using port 8000
- Or change port: `-p 8001:8000`

**Can't connect to database?**
- Make sure PostgreSQL is running
- Check DATABASE_URL environment variable
- For docker-compose, wait for database to be healthy

**Need more help?**
- See `DOCKER_DEPLOYMENT_GUIDE.md` for detailed instructions
- Check Docker logs: `docker logs hms-container`

---

## 🎉 Success!

Your HMS is now running in Docker! 🐳

**Next steps:**
1. Create superuser: `docker exec -it hms-container python manage.py createsuperuser`
2. Run migrations: `docker exec hms-container python manage.py migrate`
3. Access admin panel and configure your hospital

---

**Ready?** Run `docker-build-push.bat` (Windows) or `./docker-build-push.sh` (Linux/Mac) now! 🚀

