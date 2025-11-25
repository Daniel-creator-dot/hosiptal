# Complete Folder Structure Report

**Generated:** 2025-11-19  
**Project:** Hospital Management System (HMS)

## 📁 Main Project Folders

### Root Directory (`C:\Users\user\chm\`)
- **Docker Configuration:**
  - `docker-compose.yml` - Docker services configuration
  - `Dockerfile` - Container build configuration
  - `docker-start.bat` / `docker-start.sh` - Docker startup scripts

- **Database Files:**
  - `database_summary_local.json` - Database summary export
  - `hms_data_export.json` - Patient data export
  - `db.sqlite3` - SQLite database (if used)
  - `check_patient.sql` - SQL queries
  - `create_accounting_tables.sql` - Accounting table creation
  - `create_biometric_tables.sql` - Biometric table creation

- **Backup Files:**
  - `backups/` - Database backups directory
    - `backup_20251103_191916/` - Manual backup from Nov 3
    - `database/db_auto_backup_20251111_215301.sqlite3` - Auto backup from Nov 11

- **Deployment:**
  - `deployment/` - Deployment scripts and configs
    - `backup-hms.sh` - Backup script
    - `deploy.sh` - Deployment script
    - `hms-nginx.conf` - Nginx configuration
    - `hms.conf` - Application configuration

### 📂 Core Application Folders

#### `hospital/` - Main Application
- **Models** (30+ model files):
  - `models.py` - Core models (Patient, Encounter, etc.)
  - `models_accounting.py` - Accounting models
  - `models_advanced.py` - Advanced features
  - `models_biometric.py` - Biometric system
  - `models_queue.py` - Queue system
  - `models_hr.py` - HR management
  - `models_insurance.py` - Insurance management
  - And 20+ more specialized model files

- **Views** (80+ view files):
  - `views.py` - Main views
  - `views_role_specific.py` - Role-based dashboards
  - `views_accounting.py` - Accounting views
  - `views_advanced.py` - Advanced features
  - `views_queue.py` - Queue management
  - And 70+ more view files

- **Admin** (20+ admin files):
  - `admin.py` - Main admin
  - `admin_accounting.py` - Accounting admin
  - `admin_hr.py` - HR admin
  - And 18+ more admin files

- **Services** (`hospital/services/`):
  - `sms_service.py` - SMS sending service
  - `accounting_sync_service.py` - Accounting sync
  - `queue_service.py` - Queue management
  - `biometric_service.py` - Biometric operations
  - `payment_clearance_service.py` - Payment processing
  - `auto_billing_service.py` - Auto billing
  - And 15+ more services

- **Management Commands** (`hospital/management/commands/`):
  - **Database:**
    - `check_database_sync.py` - Check sync status
    - `export_database_summary.py` - Export summary
    - `compare_databases.py` - Compare databases
    - `show_client_data.py` - Show client data
    - `backup_database.py` - Backup database
    - `restore_database.py` - Restore database
  
  - **Data Import/Export:**
    - `import_legacy_patients.py` - Import legacy patients
    - `import_legacy_database.py` - Import legacy database
    - `export_data.py` - Export data
    - `import_staff.py` - Import staff
    - `import_insurance_data.py` - Import insurance
  
  - **SMS:**
    - `check_sms_failures.py` - Check SMS failures
    - `test_sms_api.py` - Test SMS API
    - `fix_sms_phone_numbers.py` - Fix phone numbers
    - `update_sms_api_key.py` - Update API key
  
  - **System:**
    - `clear_all_caches.py` - Clear caches
    - `fix_server_errors.py` - Fix server errors
    - `seed_data.py` - Seed sample data
    - `setup_accounting_accounts.py` - Setup accounting
    - And 50+ more commands

- **Templates** (`hospital/templates/hospital/`):
  - 372 HTML template files
  - Dashboard templates
  - Form templates
  - Report templates
  - Admin templates

- **Migrations** (`hospital/migrations/`):
  - 100+ migration files
  - All migrations applied ✅

#### `hms/` - Django Project Settings
- `settings.py` - Main settings
- `urls.py` - URL routing
- `wsgi.py` - WSGI configuration
- `celery.py` - Celery configuration

### 📊 Data Files

#### JSON Exports:
- `database_summary_local.json` - Complete database summary
- `hms_data_export.json` - Patient data export

#### SQL Files:
- `check_patient.sql` - Patient queries
- `create_accounting_tables.sql` - Accounting setup
- `create_biometric_tables.sql` - Biometric setup

#### Backup Files:
- `backups/backup_20251103_191916/` - Full backup (Nov 3)
- `backups/database/db_auto_backup_20251111_215301.sqlite3` - Auto backup (Nov 11)

### 📝 Documentation Files

**367+ Markdown documentation files** including:
- Deployment guides
- Feature documentation
- Fix summaries
- System guides
- API documentation

### 🔧 Configuration Files

- `requirements.txt` - Python dependencies
- `env.example` - Environment variables example
- `env.render.example` - Render deployment config
- `.gitignore` - Git ignore rules

### 📦 Static & Media Files

- `staticfiles/` - Collected static files
- `media/` - User uploaded media files
- `logs/` - Application logs

## 📊 Key Statistics

- **Total Models:** 285
- **Total Records:** 238
- **Management Commands:** 80+
- **View Files:** 80+
- **Service Files:** 20+
- **Template Files:** 372
- **Documentation Files:** 367+

## ✅ Database Status

- **Database:** PostgreSQL 15.15 (hms_db)
- **Migrations:** All applied ✅
- **Connection:** OK ✅
- **Client Data:** 3 Patients, 2 Encounters, 1 Invoice

## 🎯 Important Folders for Client Data

1. **`hospital/models.py`** - Patient model definition
2. **`hospital/views.py`** - Patient views
3. **`hospital/admin.py`** - Patient admin
4. **`backups/`** - Database backups
5. **`database_summary_local.json`** - Current database summary

## 🔍 Quick Commands to Check Folders

```bash
# Check database sync
docker-compose exec web python manage.py check_database_sync

# Show client data
docker-compose exec web python manage.py show_client_data

# Export database summary
docker-compose exec web python manage.py export_database_summary

# List all management commands
docker-compose exec web python manage.py help
```

## 📋 Next Steps

1. ✅ All client data is present in database
2. ✅ All migrations are applied
3. ✅ Database connection is working
4. ⚠️ Consider backing up before server deployment
5. ⚠️ Export summary for server comparison



