# 🔄 Restart Docker and Django - Step by Step

## Quick Method (Recommended)

### Step 1: Restart Docker Desktop Manually
1. Open Docker Desktop
2. Click the **Settings** icon (gear)
3. Click **"Restart"** or close and reopen Docker Desktop
4. Wait for Docker to fully start (whale icon in system tray should be steady)

### Step 2: Run the Restart Script
```powershell
cd D:\chm
.\restart_docker_django_simple.ps1
```

This will:
- ✅ Stop Docker containers
- ✅ Start Docker containers
- ✅ Run migrations
- ✅ Import JERRY.xlsx data
- ✅ Start Django server

---

## Manual Method (If Script Fails)

### Step 1: Stop Docker Containers
```powershell
cd D:\chm
docker-compose down
```

### Step 2: Restart Docker Desktop
- Open Docker Desktop
- Click "Restart" or close and reopen
- Wait for it to fully start

### Step 3: Start Docker Containers
```powershell
docker-compose up -d
```

### Step 4: Wait for Database (10 seconds)
```powershell
Start-Sleep -Seconds 10
```

### Step 5: Run Migrations
```powershell
python manage.py migrate
```

### Step 6: Import JERRY.xlsx
```powershell
python fix_and_import_jerry.py
```

### Step 7: Start Django Server
```powershell
python manage.py runserver 0.0.0.0:8000
```

---

## Verify Everything is Working

After restart, check:

1. **Docker Containers Running:**
   ```powershell
   docker-compose ps
   ```
   Should show: db, redis, web, celery, celery-beat, minio (all "Up")

2. **Django Server:**
   - Open browser: http://192.168.2.216:8000
   - Should see login page

3. **JERRY.xlsx Import:**
   - Go to: http://192.168.2.216:8000/hms/accountant/insurance-receivable/
   - Should see imported insurance receivable entries

4. **Balance Sheet:**
   - Go to: http://192.168.2.216:8000/hms/accounting/balance-sheet/
   - Should show Insurance Receivables and Accounts Payable

---

## Troubleshooting

### Docker Desktop Won't Start
- Check if virtualization is enabled in BIOS
- Restart your computer
- Check Windows WSL2 is installed

### Containers Won't Start
```powershell
# Check Docker logs
docker-compose logs

# Restart specific service
docker-compose restart db
```

### Database Connection Error
```powershell
# Check if database is ready
docker-compose exec db pg_isready -U hms_user

# Restart database
docker-compose restart db
```

### Import Fails
```powershell
# Check if table exists
python check_jerry_import_status.py

# Run fix script
python fix_and_import_jerry.py
```

---

## Quick Commands Reference

```powershell
# Stop everything
docker-compose down

# Start everything
docker-compose up -d

# View logs
docker-compose logs -f

# Restart specific service
docker-compose restart db
docker-compose restart web

# Check status
docker-compose ps

# Run migrations
python manage.py migrate

# Import JERRY.xlsx
python fix_and_import_jerry.py

# Start Django
python manage.py runserver 0.0.0.0:8000
```


