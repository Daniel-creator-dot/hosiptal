# Fix Django Server Startup Issues

## Problem
Django server cannot start because PostgreSQL database is not running.

## Error Message
```
psycopg2.OperationalError: connection to server at "localhost" (::1), port 5432 failed: Connection refused
```

## Solutions

### Option 1: Start PostgreSQL Service (Windows)

1. **Check if PostgreSQL service exists:**
   ```powershell
   Get-Service -Name "*postgresql*"
   ```

2. **Start PostgreSQL service:**
   ```powershell
   Start-Service postgresql-x64-XX  # Replace XX with your version number
   ```

3. **Or start via Services:**
   - Press `Win + R`, type `services.msc`
   - Find "PostgreSQL" service
   - Right-click → Start

### Option 2: Start PostgreSQL via Docker

If you have Docker installed:

```powershell
cd d:\chm
docker-compose up -d
```

### Option 3: Manual PostgreSQL Start

If PostgreSQL is installed but not as a service:

1. Find PostgreSQL installation directory (usually `C:\Program Files\PostgreSQL\XX\bin`)
2. Run:
   ```powershell
   pg_ctl -D "C:\Program Files\PostgreSQL\XX\data" start
   ```

### Option 4: Use Startup Scripts

I've created startup scripts for you:

1. **PowerShell Script (Recommended):**
   ```powershell
   cd d:\chm
   .\start_all_services.ps1
   ```

2. **Batch File:**
   ```powershell
   cd d:\chm
   .\start_server_with_db_check.bat
   ```

3. **Simple Batch File:**
   ```powershell
   cd d:\chm
   .\start_server.bat
   ```

## Verify Database Connection

After starting PostgreSQL, verify connection:

```powershell
cd d:\chm
python manage.py dbshell
```

If this works, the database is connected.

## Start Django Server

Once PostgreSQL is running:

```powershell
cd d:\chm
python manage.py runserver 0.0.0.0:8000
```

## Database Configuration

Default database settings (from `hms/settings.py`):
- **Host:** localhost
- **Port:** 5432
- **Database:** hms_db
- **User:** hms_user
- **Password:** hms_password

To change these, create a `.env` file in `d:\chm\`:

```env
DATABASE_URL=postgresql://hms_user:hms_password@localhost:5432/hms_db
```

## Quick Fix Summary

1. **Start PostgreSQL** (choose one method above)
2. **Wait 5-10 seconds** for PostgreSQL to fully start
3. **Run:** `cd d:\chm; python manage.py runserver 0.0.0.0:8000`

The server should now start successfully!
