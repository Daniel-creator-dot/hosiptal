# Drug Accountability System - Deployment Checklist

## Files That Must Be Deployed

1. ✅ `hospital/urls.py` - Updated with drug accountability URLs
2. ✅ `hospital/views_drug_accountability.py` - All accountability views
3. ✅ `hospital/views_departments.py` - Updated pharmacy dashboard
4. ✅ `hospital/templates/hospital/pharmacy_dashboard_worldclass.html` - Updated template
5. ✅ `hospital/models_drug_accountability.py` - Drug accountability models
6. ✅ `hospital/migrations/1058_add_drug_accountability_system.py` - Database migration

## Deployment Steps

### 1. Copy Files to Remote Server
```bash
# Copy these files to your remote server:
scp hospital/urls.py user@server:/app/hospital/
scp hospital/views_drug_accountability.py user@server:/app/hospital/
scp hospital/views_departments.py user@server:/app/hospital/
scp hospital/templates/hospital/pharmacy_dashboard_worldclass.html user@server:/app/hospital/templates/hospital/
scp hospital/models_drug_accountability.py user@server:/app/hospital/
scp hospital/migrations/1058_add_drug_accountability_system.py user@server:/app/hospital/migrations/
```

### 2. Run Database Migration
```bash
# SSH into remote server
ssh user@server
cd /app
python manage.py migrate hospital 1058_add_drug_accountability_system
```

### 3. Restart Django Server
```bash
# Stop current server (Ctrl+C or kill process)
# Then restart:
python manage.py runserver 0.0.0.0:8000

# Or if using systemd:
sudo systemctl restart your-django-service

# Or if using Docker:
docker-compose restart
```

### 4. Verify URLs Are Registered
```bash
# On remote server, test URL resolution:
python manage.py shell
>>> from django.urls import reverse
>>> reverse('hospital:drug_returns_list')
'/hms/drug-returns/'
```

## Troubleshooting

### If URLs Still Return 404:
1. Check server logs for import errors
2. Verify `views_drug_accountability.py` exists in `/app/hospital/`
3. Check Python path includes `/app`
4. Restart server after file deployment

### If Database Error:
- Run migration: `python manage.py migrate hospital 1058_add_drug_accountability_system`

### If Import Error:
- The URLs will still work with dummy views that redirect to pharmacy dashboard
- Check that all required model files exist

## Expected Behavior

- **Before Migration**: URLs work but redirect to pharmacy dashboard with message
- **After Migration**: All URLs work normally with full functionality







