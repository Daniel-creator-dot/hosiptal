# Database Sync Status Report

**Generated:** 2025-11-19  
**Database:** hms_db (PostgreSQL 15.15)

## Summary

Your local database contains **238 total records** across **285 models**.

### ✅ Key Client/Patient Data Status

| Model | Count | Status |
|-------|-------|--------|
| **Patients** | 3 | ✅ Present |
| **Encounters** | 2 | ✅ Present |
| **Invoices** | 1 | ✅ Present |
| **Lab Tests** | 1 | ✅ Present |
| **Lab Results** | 2 | ✅ Present |
| **Prescriptions** | 2 | ✅ Present |
| **Payment Receipts** | 0 | ⚠️ Empty |
| **Appointments** | 0 | ⚠️ Empty |

### Patient Details

1. **PMC2025000001**: Anthony Amissah (Created: 2025-10-28 17:23)
2. **PMC2025000002**: Anthony Amissah (Created: 2025-10-28 17:25)
3. **PMC2025000003**: afua kuoomson (Created: 2025-10-28 20:25)

## Database Status

✅ **All migrations are applied**  
✅ **Database connection: OK**  
✅ **No pending migrations**

## Available Tools

### 1. Check Database Sync Status
```bash
docker-compose exec web python manage.py check_database_sync
```

### 2. Show Client Data Summary
```bash
docker-compose exec web python manage.py show_client_data
```

### 3. Export Database Summary
```bash
docker-compose exec web python manage.py export_database_summary --output database_summary.json
```

### 4. Compare Local vs Server
```bash
# On local machine
docker-compose exec web python manage.py export_database_summary --output database_summary_local.json

# On server (after copying the command)
python manage.py export_database_summary --output database_summary_server.json

# Compare
docker-compose exec web python manage.py compare_databases --local database_summary_local.json --server database_summary_server.json
```

## Next Steps

### If You Need to Push to a Remote Server:

1. **Export Database Backup:**
   ```bash
   docker-compose exec web python manage.py backup_database --output-dir backups/
   ```

2. **Or use PostgreSQL dump directly:**
   ```bash
   docker-compose exec db pg_dump -U hms_user hms_db > backup_$(date +%Y%m%d_%H%M%S).sql
   ```

3. **Transfer to Server:**
   - Copy the backup file to your server
   - Restore on server using:
     ```bash
     psql -U hms_user -d hms_db < backup_file.sql
     ```

### If You're Using Docker on Server:

The database is already in the Docker container. If you're deploying to a server:
1. Make sure all code changes are pushed to the server
2. Run migrations on server: `docker-compose exec web python manage.py migrate`
3. The database data is stored in Docker volumes, so it persists

## Important Notes

⚠️ **Empty Models (Expected):**
- PaymentReceipt: 0 (no payments recorded yet)
- Appointments: 0 (no appointments scheduled)
- QueueEntry: 0 (using older Queue model with 8 entries)
- CorporateAccount: 0 (not configured)
- InsuranceCompany: 0 (not configured)

✅ **All client/patient data is present and accounted for.**

## Files Generated

- `database_summary_local.json` - Complete database summary for comparison
- `DATABASE_SYNC_REPORT.md` - This report



