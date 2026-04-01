# 🚀 QUICK DEPLOYMENT - Copy & Paste Commands

## Option 1: Automated Deployment (Recommended)

### On Your Local Windows Machine:

```powershell
# Make sure you're in the project directory
cd D:\chm

# Run the deployment script
.\deploy_to_remote.ps1
```

**Note:** You may need to update the `$Server` variable in the script with your actual SSH credentials.

### On Your Remote Server:

```bash
# SSH into server
ssh user@192.168.2.216
cd /app

# Copy the deployment script to server (if not already there)
# Then run:
chmod +x deploy_and_migrate.sh
./deploy_and_migrate.sh
```

## Option 2: Manual Step-by-Step

### Step 1: Copy Files (From Local Windows)

```powershell
# Set your server details
$server = "user@192.168.2.216"

# Copy files
scp hospital/urls.py ${server}:/app/hospital/
scp hospital/views_drug_accountability.py ${server}:/app/hospital/
scp hospital/views_departments.py ${server}:/app/hospital/
scp hospital/models_drug_accountability.py ${server}:/app/hospital/
scp hospital/migrations/1058_add_drug_accountability_system.py ${server}:/app/hospital/migrations/
scp hospital/templates/hospital/pharmacy_dashboard_worldclass.html ${server}:/app/hospital/templates/hospital/
```

### Step 2: Run Migration (On Remote Server)

```bash
# SSH into server
ssh user@192.168.2.216
cd /app

# Run migration
python manage.py migrate hospital 1058_add_drug_accountability_system

# Verify migration
python manage.py showmigrations hospital | grep 1058
```

### Step 3: Restart Server

```bash
# Stop current server (Ctrl+C or find process)
ps aux | grep "manage.py runserver"
# Kill if needed: kill <PID>

# Restart
python manage.py runserver 0.0.0.0:8000
```

## Option 3: One-Liner (If you have SSH keys set up)

```bash
# From local machine, copy files and run migration in one go
scp hospital/{urls.py,views_drug_accountability.py,views_departments.py,models_drug_accountability.py} user@192.168.2.216:/app/hospital/ && \
scp hospital/migrations/1058_add_drug_accountability_system.py user@192.168.2.216:/app/hospital/migrations/ && \
scp hospital/templates/hospital/pharmacy_dashboard_worldclass.html user@192.168.2.216:/app/hospital/templates/hospital/ && \
ssh user@192.168.2.216 "cd /app && python manage.py migrate hospital 1058_add_drug_accountability_system && echo 'Migration complete! Restart your server.'"
```

## Verification

After deployment, test:
- http://192.168.2.216:8000/hms/drug-returns/ (should work or redirect with message)
- http://192.168.2.216:8000/hms/pharmacy/ (should load without errors)







