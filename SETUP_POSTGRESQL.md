# PostgreSQL Desktop Setup Guide

## Current Status
❌ PostgreSQL Desktop is NOT running on port 5432
❌ .env file is configured for SQLite instead of PostgreSQL

## Step 1: Start PostgreSQL Desktop

1. **Open PostgreSQL Desktop** (pgAdmin or your PostgreSQL application)
2. **Start the PostgreSQL server:**
   - In pgAdmin: Right-click on your server → "Connect Server"
   - Or check Windows Services: `services.msc` → Find "PostgreSQL" → Start

3. **Verify it's running:**
   ```powershell
   Test-NetConnection -ComputerName localhost -Port 5432
   ```
   Should show: `TcpTestSucceeded : True`

## Step 2: Create Database

1. **Open pgAdmin**
2. **Connect to your PostgreSQL server**
3. **Create the database:**
   - Right-click "Databases" → Create → Database
   - Name: `hms_db`
   - Owner: `postgres` (or your PostgreSQL user)
   - Click "Save"

## Step 3: Update .env File

The .env file needs to be updated with your PostgreSQL credentials.

**Common PostgreSQL Desktop defaults:**
- Username: `postgres`
- Password: `postgres` (or the password you set during installation)
- Host: `host.docker.internal` (for Docker) or `localhost` (for direct access)
- Port: `5432`
- Database: `hms_db`

**Update .env file:**
```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@host.docker.internal:5432/hms_db
```

Replace `YOUR_PASSWORD` with your actual PostgreSQL password.

## Step 4: Test Connection

After updating .env and starting PostgreSQL:

```bash
# Restart Docker services
docker-compose restart web

# Test connection
docker-compose exec web python manage.py dbshell
```

If successful, you'll see the PostgreSQL prompt: `hms_db=#`

## Step 5: Run Migrations

Once connected to PostgreSQL:

```bash
docker-compose exec web python manage.py migrate
```

## Troubleshooting

### PostgreSQL not starting?
- Check Windows Services: `services.msc`
- Look for "PostgreSQL" service
- Right-click → Start

### Can't connect from Docker?
- Make sure PostgreSQL is listening on all interfaces
- Check `postgresql.conf`: `listen_addresses = '*'`
- Check `pg_hba.conf`: Allow connections from Docker network

### Connection refused?
- Verify PostgreSQL is running: `netstat -an | findstr 5432`
- Check firewall settings
- Make sure port 5432 is not blocked

### Wrong password?
- Reset PostgreSQL password in pgAdmin
- Update .env file with correct password















