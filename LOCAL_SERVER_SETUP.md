# Local Server Setup - No Docker

## ✅ Docker Stopped

Docker containers have been stopped. The system is now configured to run locally.

## Database Configuration

The system is configured to use PostgreSQL on **localhost:5432**:
- **Host:** localhost
- **Port:** 5432
- **Database:** hms_db
- **User:** hms_user
- **Password:** hms_password

## Prerequisites

### 1. PostgreSQL Must Be Running

You have two options:

#### Option A: Use Docker Database Only (Recommended)
```bash
# Start only the PostgreSQL database container
docker-compose up -d db
```

This starts PostgreSQL in Docker but runs Django locally.

#### Option B: Install PostgreSQL Locally
- Install PostgreSQL on Windows
- Create database: `hms_db`
- Create user: `hms_user` with password: `hms_password`
- Start PostgreSQL service

## Starting the Local Server

### Quick Start (Windows)
```bash
START_LOCAL_SERVER.bat
```

### Manual Start
```bash
# Activate virtual environment (if using one)
venv\Scripts\activate

# Run migrations
python manage.py migrate

# Start server
python manage.py runserver 0.0.0.0:8000
```

## Access the Application

- **URL:** http://localhost:8000
- **Admin:** http://localhost:8000/admin
- **Patient Registration:** http://localhost:8000/hms/patients/new/

## Benefits of Local Server

1. ✅ **Faster development** - No Docker overhead
2. ✅ **Easier debugging** - Direct access to code
3. ✅ **Better IDE integration** - Full debugging support
4. ✅ **No duplicate issues** - Single server instance

## Troubleshooting

### Cannot Connect to Database
```bash
# Check if PostgreSQL is running
netstat -ano | findstr :5432

# Start Docker database if needed
docker-compose up -d db
```

### Port 8000 Already in Use
```bash
# Find what's using port 8000
netstat -ano | findstr :8000

# Kill the process or use different port
python manage.py runserver 0.0.0.0:8001
```

### Migration Errors
```bash
# Reset migrations (if needed)
python manage.py migrate --fake-initial
```

## Stopping Docker (If Needed)

If you want to completely stop Docker:
```bash
docker-compose down
```

But keep the database running:
```bash
docker-compose up -d db
```

## Current Configuration

- **Server:** Local Django development server
- **Database:** PostgreSQL (localhost:5432)
- **Mode:** Development (DEBUG=True)
- **Port:** 8000

