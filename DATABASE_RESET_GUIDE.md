# 🗄️ Complete Database Reset Guide

This guide explains how to completely reset your PostgreSQL database and start fresh.

## ⚠️ WARNING

**This will DELETE ALL DATA in your database!** Make sure you have backups if you need to preserve any data.

---

## 🚀 Quick Start

### Option 1: Direct PostgreSQL Reset (Recommended)

If you have PostgreSQL installed locally:

1. **Run the reset script:**
   ```bash
   # Windows
   RESET_DATABASE.bat
   
   # Or manually
   python reset_database_complete.py
   ```

2. **Follow the prompts** - The script will:
   - Drop all existing databases
   - Create a fresh PostgreSQL database
   - Run all Django migrations
   - Update your .env file

3. **Create a superuser:**
   ```bash
   python manage.py createsuperuser
   ```

### Option 2: Docker-based Reset

If you're using Docker:

1. **Run the Docker reset script:**
   ```bash
   # Windows
   RESET_DATABASE_DOCKER.bat
   
   # Or manually
   python reset_database_docker.py
   ```

2. **The script will:**
   - Stop all Docker services
   - Remove the database volume
   - Start services fresh
   - Run all migrations

3. **Create a superuser:**
   ```bash
   docker-compose exec web python manage.py createsuperuser
   ```

---

## 📋 Prerequisites

### For Direct PostgreSQL Reset:

1. **PostgreSQL installed and running**
   - Default: `localhost:5432`
   - User: `postgres` (or your admin user)
   - Password: Your PostgreSQL admin password

2. **Python packages:**
   ```bash
   pip install psycopg2-binary
   ```

3. **Environment variables (optional):**
   ```bash
   set DB_HOST=localhost
   set DB_PORT=5432
   set DB_USER=postgres
   set DB_PASSWORD=your_password
   set TARGET_DB=hms_db
   set TARGET_USER=hms_user
   set TARGET_PASSWORD=hms_password
   ```

### For Docker Reset:

1. **Docker Desktop installed and running**
2. **docker-compose available**

---

## 🔧 Manual Reset Steps

If you prefer to do it manually:

### Step 1: Connect to PostgreSQL

```bash
psql -U postgres -h localhost
```

### Step 2: Drop the Database

```sql
-- Terminate all connections
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'hms_db' AND pid <> pg_backend_pid();

-- Drop the database
DROP DATABASE IF EXISTS hms_db;
```

### Step 3: Create Fresh Database

```sql
-- Create user (if doesn't exist)
CREATE USER hms_user WITH PASSWORD 'hms_password';

-- Create database
CREATE DATABASE hms_db OWNER hms_user;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE hms_db TO hms_user;
```

### Step 4: Run Migrations

```bash
python manage.py migrate
```

### Step 5: Create Superuser

```bash
python manage.py createsuperuser
```

---

## 🐳 Docker Manual Reset

### Step 1: Stop Services

```bash
docker-compose down
```

### Step 2: Remove Database Volume

```bash
docker-compose volume rm chm_postgres_data
```

### Step 3: Start Services

```bash
docker-compose up -d
```

### Step 4: Run Migrations

```bash
docker-compose exec web python manage.py migrate
```

### Step 5: Create Superuser

```bash
docker-compose exec web python manage.py createsuperuser
```

---

## ✅ Verification

After resetting, verify everything works:

1. **Check database connection:**
   ```bash
   python manage.py dbshell
   ```

2. **Check migrations:**
   ```bash
   python manage.py showmigrations
   ```

3. **Start the server:**
   ```bash
   python manage.py runserver
   ```

4. **Access the admin:**
   - Go to: `http://localhost:8000/admin/`
   - Login with your superuser credentials

---

## 🔍 Troubleshooting

### Error: "Could not connect to PostgreSQL"

**Solution:**
- Verify PostgreSQL is running: `pg_isready` or check services
- Check connection details in the script
- Verify firewall settings
- For Docker: Ensure Docker Desktop is running

### Error: "Database already exists"

**Solution:**
- The script should drop it first, but if it persists:
  - Manually drop: `DROP DATABASE hms_db;`
  - Or use the reset script again

### Error: "Permission denied"

**Solution:**
- Ensure you're using a PostgreSQL superuser (usually `postgres`)
- Check user permissions
- For Docker: Ensure Docker has proper permissions

### Error: "Migrations failed"

**Solution:**
- Check Django settings are correct
- Verify DATABASE_URL in .env file
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check migration files are present in `hospital/migrations/`

---

## 📝 Configuration Files

### .env File

After reset, your `.env` file should contain:

```env
DATABASE_URL=postgresql://hms_user:hms_password@localhost:5432/hms_db
```

### docker-compose.yml

The Docker configuration uses:
- Database: `hms_db`
- User: `hms_user`
- Password: `hms_password`
- Host: `db` (inside Docker) or `localhost` (from host)

---

## 🎯 Next Steps After Reset

1. **Create initial data:**
   ```bash
   python manage.py createsuperuser
   ```

2. **Load fixtures (if available):**
   ```bash
   python manage.py loaddata initial_data.json
   ```

3. **Start the server:**
   ```bash
   python manage.py runserver
   ```

4. **Or use Docker:**
   ```bash
   docker-compose up -d
   ```

---

## 📚 Additional Resources

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Django Database Setup](https://docs.djangoproject.com/en/stable/ref/databases/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)

---

## 🆘 Need Help?

If you encounter issues:

1. Check the error messages carefully
2. Verify all prerequisites are met
3. Check PostgreSQL logs
4. Review Django logs: `python manage.py check`
5. Ensure all migrations are applied: `python manage.py showmigrations`

---

**Last Updated:** 2025-01-27

