# Database Error Fix Guide

This guide helps you identify and fix database errors in the Hospital Management System.

## Quick Start

### Option 1: Use the Management Command (Recommended)
```bash
# Check for errors only
python manage.py fix_database --check-only

# Fix migrations automatically
python manage.py fix_database --fix-migrations

# Fix constraints
python manage.py fix_database --fix-constraints

# Fix everything
python manage.py fix_database --fix-migrations --fix-constraints
```

### Option 2: Use the Standalone Script
```bash
python fix_database_errors.py
```

## Common Database Errors and Fixes

### 1. Missing Tables
**Error:** `relation "hospital_xxx" does not exist`

**Fix:**
```bash
python manage.py migrate
```

### 2. Missing Columns
**Error:** `column "xxx" does not exist`

**Fix:**
```bash
python manage.py makemigrations hospital
python manage.py migrate
```

### 3. Foreign Key Constraint Violations
**Error:** `insert or update on table violates foreign key constraint`

**Fix:**
1. Check for orphaned records:
```bash
python manage.py fix_database --check-only
```

2. Manually fix orphaned records or run:
```bash
python manage.py fix_database --fix-constraints
```

### 4. Migration Conflicts
**Error:** `Migration conflicts detected`

**Fix:**
```bash
# Show migration status
python manage.py showmigrations hospital

# Create new migrations
python manage.py makemigrations hospital

# Apply migrations
python manage.py migrate
```

### 5. Database Connection Errors
**Error:** `could not connect to server` or `password authentication failed`

**Fix:**
1. Check `.env` file has correct `DATABASE_URL`
2. Verify PostgreSQL is running
3. Check database credentials
4. Test connection:
```bash
python check_database.py
```

## What the Fix Scripts Check

### 1. Database Connection
- Verifies database connectivity
- Checks connection settings

### 2. Missing Tables
Checks for critical tables:
- `hospital_patient`
- `hospital_staff`
- `hospital_invoice`
- `hospital_generalledger`
- `hospital_journalentry`
- `hospital_transaction`

### 3. Missing Columns
Checks for critical columns:
- `hospital_generalledger.balance`
- `hospital_generalledger.reference_number`
- `hospital_journalentry.entry_type`
- `hospital_journalentry.reference_number`
- `hospital_journalentry.posted_by_id`
- `hospital_journalentry.status`

### 4. Foreign Key Constraints
- Validates foreign key relationships
- Checks for broken references

### 5. Migration Status
- Verifies all migrations are applied
- Identifies unapplied migrations

### 6. Orphaned Records
- Finds records with broken foreign key references
- Identifies data integrity issues

## Step-by-Step Fix Process

1. **Check Current Status**
   ```bash
   python manage.py fix_database --check-only
   ```

2. **Create Missing Migrations**
   ```bash
   python manage.py makemigrations hospital
   ```

3. **Apply Migrations**
   ```bash
   python manage.py migrate
   ```

4. **Verify Fixes**
   ```bash
   python manage.py fix_database --check-only
   ```

## Advanced Troubleshooting

### Reset Migrations (Use with Caution!)
```bash
# Backup database first!
python manage.py migrate hospital zero
python manage.py migrate hospital
```

### Check Specific Table
```sql
-- Connect to database
python manage.py dbshell

-- Check table structure
\d hospital_generalledger

-- Check for missing columns
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'hospital_generalledger';
```

### Fix Orphaned Records
```sql
-- Example: Fix orphaned invoice lines
DELETE FROM hospital_invoiceline 
WHERE invoice_id NOT IN (SELECT id FROM hospital_invoice);
```

## Prevention

1. **Always run migrations after model changes**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

2. **Test migrations in development first**
   ```bash
   python manage.py migrate --plan
   ```

3. **Backup database before major migrations**
   ```bash
   pg_dump -h localhost -U user -d database > backup.sql
   ```

4. **Use transactions for data migrations**
   - Django migrations are automatically wrapped in transactions
   - For custom scripts, use `@transaction.atomic`

## Getting Help

If you encounter errors:

1. Check the error message carefully
2. Run `python manage.py fix_database --check-only` to identify issues
3. Check migration status: `python manage.py showmigrations`
4. Review recent model changes
5. Check database logs

## Files

- `fix_database_errors.py` - Standalone diagnostic script
- `hospital/management/commands/fix_database.py` - Django management command
- `check_database.py` - Database connection checker
- `hospital/management/commands/check_database_sync.py` - Schema sync checker

