# Quick Start: PostgreSQL Desktop + Docker Desktop

## ✅ What's Been Configured

Your project is now set up to use:
- **PostgreSQL Desktop** (running on your Windows machine)
- **Docker Desktop** (for Redis, Django app, Celery, etc.)

## 🚀 Quick Start (3 Steps)

### Step 1: Create `.env` File

Copy the example file and update with your PostgreSQL credentials:

```bash
copy env.local.example .env
```

Then edit `.env` and update:
```env
DATABASE_URL=postgresql://YOUR_USERNAME:YOUR_PASSWORD@host.docker.internal:5432/YOUR_DATABASE
```

**Common PostgreSQL Desktop defaults:**
- Username: `postgres`
- Password: `postgres` (or the password you set during installation)
- Database: `hms_db` (create it first in pgAdmin)

### Step 2: Create Database in PostgreSQL Desktop

1. Open **pgAdmin** (PostgreSQL Desktop)
2. Connect to your PostgreSQL server
3. Right-click "Databases" → Create → Database
4. Name: `hms_db`
5. Click Save

### Step 3: Start Everything

**Option A: Use the batch script (Windows)**
```bash
start-docker.bat
```

**Option B: Manual commands**
```bash
# Build and start
docker-compose build
docker-compose up -d

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser (optional)
docker-compose exec web python manage.py createsuperuser
```

## 🌐 Access Your Application

Open your browser: **http://localhost:8000**

## 📋 Common Commands

```bash
# View logs
docker-compose logs -f web

# Stop all services
docker-compose down

# Restart services
docker-compose restart

# Run Django commands
docker-compose exec web python manage.py <command>

# Access Django shell
docker-compose exec web python manage.py shell

# Access database shell
docker-compose exec web python manage.py dbshell
```

## 🔧 Troubleshooting

### Can't connect to PostgreSQL?

1. **Check PostgreSQL is running:**
   - Open pgAdmin and verify server is running
   - Check Windows Services: `services.msc` → Find PostgreSQL → Should be "Running"

2. **Check port 5432 is open:**
   ```bash
   netstat -an | findstr 5432
   ```

3. **Update `.env` with correct credentials:**
   ```env
   DATABASE_URL=postgresql://postgres:postgres@host.docker.internal:5432/hms_db
   ```

4. **Test connection from Docker:**
   ```bash
   docker-compose exec web python manage.py dbshell
   ```

### Services won't start?

```bash
# Check what's wrong
docker-compose logs

# Rebuild everything
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## 📚 Full Documentation

See `POSTGRESQL_DOCKER_SETUP.md` for detailed setup instructions.

## 🏗️ Architecture

```
Windows Host
├── PostgreSQL Desktop (Port 5432)
│   └── Database: hms_db
│
└── Docker Desktop
    ├── Web (Django) → Port 8000
    ├── Celery Worker
    ├── Celery Beat
    ├── Redis → Port 6379
    └── MinIO → Ports 9000, 9001
```

All Docker services connect to PostgreSQL Desktop via `host.docker.internal:5432`















