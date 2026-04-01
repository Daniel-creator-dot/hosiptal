# Drug Accountability System - Complete Deployment Guide

## Quick Deployment (Remote Server)

### Option 1: Using the Deployment Script

1. **Copy the deployment script to your remote server:**
   ```bash
   scp deploy_drug_accountability.sh user@192.168.2.216:/app/
   ```

2. **SSH into your remote server:**
   ```bash
   ssh user@192.168.2.216
   cd /app
   ```

3. **Make the script executable and run it:**
   ```bash
   chmod +x deploy_drug_accountability.sh
   ./deploy_drug_accountability.sh
   ```

### Option 2: Manual Deployment

1. **Copy all required files to remote server:**
   ```bash
   # From your local machine
   scp hospital/urls.py user@192.168.2.216:/app/hospital/
   scp hospital/views_drug_accountability.py user@192.168.2.216:/app/hospital/
   scp hospital/views_departments.py user@192.168.2.216:/app/hospital/
   scp hospital/templates/hospital/pharmacy_dashboard_worldclass.html user@192.168.2.216:/app/hospital/templates/hospital/
   scp hospital/models_drug_accountability.py user@192.168.2.216:/app/hospital/
   scp hospital/migrations/1058_add_drug_accountability_system.py user@192.168.2.216:/app/hospital/migrations/
   ```

2. **SSH into remote server and run migration:**
   ```bash
   ssh user@192.168.2.216
   cd /app
   python manage.py migrate hospital 1058_add_drug_accountability_system
   ```

3. **Restart Django server:**
   ```bash
   # Stop current server (Ctrl+C or kill process)
   python manage.py runserver 0.0.0.0:8000
   ```

## Files That Must Be Deployed

✅ `hospital/urls.py` - Updated URL configuration
✅ `hospital/views_drug_accountability.py` - All accountability views (with error handling)
✅ `hospital/views_departments.py` - Updated pharmacy dashboard
✅ `hospital/templates/hospital/pharmacy_dashboard_worldclass.html` - Updated template
✅ `hospital/models_drug_accountability.py` - Drug accountability models
✅ `hospital/migrations/1058_add_drug_accountability_system.py` - Database migration

## Verification

After deployment, test these URLs:

- ✅ `http://192.168.2.216:8000/hms/drug-returns/` - Should work (or redirect with message)
- ✅ `http://192.168.2.216:8000/hms/pharmacy/` - Should load without errors
- ✅ `http://192.168.2.216:8000/hms/drug-accountability/dashboard/` - Should work

## Troubleshooting

### If migration fails:
```bash
# Check migration status
python manage.py showmigrations hospital

# If migration is already applied, fake it:
python manage.py migrate hospital 1058_add_drug_accountability_system --fake

# Or rollback and reapply:
python manage.py migrate hospital 1057_add_direct_chat_support
python manage.py migrate hospital 1058_add_drug_accountability_system
```

### If URLs still return 404:
1. Check server logs for import errors
2. Verify all files are in correct locations
3. Restart server after file deployment
4. Clear Python cache: `find . -type d -name __pycache__ -exec rm -r {} +`

### If database errors persist:
- Run: `python manage.py migrate` (to run all pending migrations)
- Check database connection
- Verify migration was applied: `python manage.py showmigrations hospital`







