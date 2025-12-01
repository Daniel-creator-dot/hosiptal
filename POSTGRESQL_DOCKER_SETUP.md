# PostgreSQL Desktop + Docker Desktop Setup Guide

This guide will help you configure your HMS application to run with **PostgreSQL Desktop** and **Docker Desktop**.

## Prerequisites

✅ **PostgreSQL Desktop** - Installed and running  
✅ **Docker Desktop** - Installed and running

## Step 1: Configure PostgreSQL Desktop

### 1.1 Start PostgreSQL Desktop
- Open **PostgreSQL Desktop** (pgAdmin or your PostgreSQL Desktop application)
- Make sure the PostgreSQL server is running

### 1.2 Create Database and User

Open **pgAdmin** or your PostgreSQL client and run these SQL commands:

```sql
-- Create database
CREATE DATABASE hms_db;

-- Create user (if not exists)
CREATE USER hms_user WITH PASSWORD 'hms_password';

-- Or use the default postgres user (update .env accordingly)
-- The default postgres user usually has password 'postgres'

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE hms_db TO hms_user;
-- Or if using postgres user, it already has all privileges
```

### 1.3 Configure PostgreSQL to Accept Connections

1. **Find PostgreSQL configuration file** (`postgresql.conf`):
   - Location varies by installation
   - Common locations:
     - `C:\Program Files\PostgreSQL\15\data\postgresql.conf`
     - Check PostgreSQL Desktop settings for data directory

2. **Edit `postgresql.conf`**:
   ```conf
   listen_addresses = '*'  # or 'localhost' for local only
   port = 5432
   ```

3. **Edit `pg_hba.conf`** (in same directory):
   ```conf
   # Allow connections from Docker containers
   host    all             all             172.16.0.0/12           md5
   host    all             all             192.168.0.0/16          md5
   host    all             all             127.0.0.1/32             md5
   ```

4. **Restart PostgreSQL**:
   - Restart PostgreSQL service from PostgreSQL Desktop
   - Or use Services app: `services.msc` → Find PostgreSQL → Restart

### 1.4 Verify PostgreSQL is Running

Test connection from command line:
```bash
psql -U postgres -h localhost -p 5432
# Or
psql -U hms_user -h localhost -p 5432 -d hms_db
```

## Step 2: Configure Environment Variables

### 2.1 Update `.env` File

Edit the `.env` file in the project root and update these values:

```env
# Update with your PostgreSQL Desktop credentials
DATABASE_URL=postgresql://postgres:postgres@host.docker.internal:5432/hms_db

# Or if you created a custom user:
# DATABASE_URL=postgresql://hms_user:hms_password@host.docker.internal:5432/hms_db
```

**Important Notes:**
- `host.docker.internal` is a special DNS name that Docker Desktop provides to access the host machine
- Replace `postgres:postgres` with your actual PostgreSQL username and password
- Replace `hms_db` with your actual database name

## Step 3: Start Docker Services

### 3.1 Start Docker Desktop
- Make sure **Docker Desktop** is running
- Wait for it to fully start (whale icon in system tray)

### 3.2 Build and Start Services

```bash
# Build the Docker images
docker-compose build

# Start all services (Redis, Web, Celery, etc.)
docker-compose up -d

# View logs
docker-compose logs -f web
```

### 3.3 Run Database Migrations

```bash
# Run migrations inside the Docker container
docker-compose exec web python manage.py migrate

# Create superuser (if needed)
docker-compose exec web python manage.py createsuperuser
```

## Step 4: Verify Everything Works

### 4.1 Check Service Status

```bash
# Check all services are running
docker-compose ps

# Check web service logs
docker-compose logs web

# Check if web service can connect to PostgreSQL
docker-compose exec web python manage.py dbshell
```

### 4.2 Access the Application

- Open browser: `http://localhost:8000`
- You should see the HMS application

## Troubleshooting

### Issue: Cannot connect to PostgreSQL from Docker

**Solution 1: Check PostgreSQL is listening on all interfaces**
```bash
# On Windows, check if PostgreSQL is listening
netstat -an | findstr 5432
```

**Solution 2: Use host network mode (Windows Docker Desktop)**
Update `docker-compose.yml` web service:
```yaml
network_mode: "host"  # Only works on Linux, not Windows
```

**Solution 3: Use Windows host IP**
Instead of `host.docker.internal`, try your actual Windows IP:
```env
DATABASE_URL=postgresql://postgres:postgres@192.168.1.100:5432/hms_db
```

### Issue: Connection refused

1. **Check PostgreSQL is running:**
   ```bash
   # Check PostgreSQL service
   sc query postgresql-x64-15
   ```

2. **Check firewall:**
   - Windows Firewall might be blocking port 5432
   - Add exception for PostgreSQL

3. **Check pg_hba.conf:**
   - Make sure it allows connections from Docker network

### Issue: Authentication failed

1. **Verify credentials in `.env`:**
   ```env
   DATABASE_URL=postgresql://username:password@host.docker.internal:5432/database
   ```

2. **Test connection directly:**
   ```bash
   psql -U postgres -h localhost -p 5432 -d hms_db
   ```

### Issue: Database does not exist

Create the database:
```sql
CREATE DATABASE hms_db;
```

## Running Without Docker (Optional)

If you want to run Django directly (not in Docker) but still use PostgreSQL Desktop:

1. **Update `.env`:**
   ```env
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/hms_db
   REDIS_URL=redis://localhost:6379/0
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run migrations:**
   ```bash
   python manage.py migrate
   ```

4. **Start development server:**
   ```bash
   python manage.py runserver
   ```

## Quick Reference Commands

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# View logs
docker-compose logs -f

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# Access Django shell
docker-compose exec web python manage.py shell

# Access database shell
docker-compose exec web python manage.py dbshell

# Rebuild after code changes
docker-compose up -d --build
```

## Architecture Overview

```
┌─────────────────────────────────────┐
│     Windows Host Machine            │
│                                     │
│  ┌──────────────────────────────┐   │
│  │  PostgreSQL Desktop          │   │
│  │  (Port 5432)                 │   │
│  └──────────────────────────────┘   │
│            ▲                         │
│            │ host.docker.internal    │
│            │                         │
│  ┌──────────────────────────────┐   │
│  │  Docker Desktop              │   │
│  │                              │   │
│  │  ┌────────────────────────┐   │   │
│  │  │  Web (Django)          │   │   │
│  │  │  Port 8000             │   │   │
│  │  └────────────────────────┘   │   │
│  │  ┌────────────────────────┐   │   │
│  │  │  Celery Worker         │   │   │
│  │  └────────────────────────┘   │   │
│  │  ┌────────────────────────┐   │   │
│  │  │  Celery Beat           │   │   │
│  │  └────────────────────────┘   │   │
│  │  ┌────────────────────────┐   │   │
│  │  │  Redis (Container)     │   │   │
│  │  │  Port 6379             │   │   │
│  │  └────────────────────────┘   │   │
│  └──────────────────────────────┘   │
└─────────────────────────────────────┘
```

## Next Steps

1. ✅ Configure PostgreSQL Desktop
2. ✅ Update `.env` file with your credentials
3. ✅ Start Docker services
4. ✅ Run migrations
5. ✅ Access application at `http://localhost:8000`

For more help, check the logs:
```bash
docker-compose logs -f web
```















