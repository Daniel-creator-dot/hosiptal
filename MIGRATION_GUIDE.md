# 🚀 Legacy Data Migration Guide

## Overview

This comprehensive migration system imports legacy MySQL database data into Django models with:
- ✅ Intelligent mapping from legacy SQL tables to Django models
- ✅ Duplicate detection and update capabilities
- ✅ Support for PostgreSQL (current) and MySQL databases
- ✅ Progress tracking and error handling
- ✅ Transaction-safe imports

## Quick Start

### Basic Migration (Using SQL Files)

```bash
python manage.py migrate_legacy_data --sql-dir import/db_3_extracted
```

This will:
1. Import patients from `patient_data.sql`
2. Import drugs from `drugs.sql`
3. Import services/codes from `codes.sql`
4. Import lab tests from `codes.sql` (where is_lab_order=1)
5. Import inventory from `drug_inventory.sql`
6. Update existing records instead of creating duplicates

### Dry Run (Preview)

```bash
python manage.py migrate_legacy_data --sql-dir import/db_3_extracted --dry-run
```

### Update Existing Records (Default)

```bash
# Updates existing records if found (default behavior)
python manage.py migrate_legacy_data --sql-dir import/db_3_extracted --update-existing
```

### Skip Duplicates

```bash
# Skips duplicates instead of updating
python manage.py migrate_legacy_data --sql-dir import/db_3_extracted --skip-duplicates
```

### Direct MySQL Connection

If you have access to the source MySQL database:

```bash
python manage.py migrate_legacy_data \
  --use-mysql \
  --mysql-host localhost \
  --mysql-user root \
  --mysql-password yourpassword \
  --mysql-database legacy_hospital
```

### Skip Specific Tables

```bash
python manage.py migrate_legacy_data \
  --sql-dir import/db_3_extracted \
  --skip-tables form_* audit_* logs_*
```

## Data Import Order

The migration runs in this order to respect foreign key dependencies:

1. **Reference Data** (Payers, Staff)
2. **Patients**
3. **Drugs/Pharmacy**
4. **Services/Codes**
5. **Lab Tests**
6. **Imaging Studies**
7. **Inventory**
8. **Billing/Charges**

## What Gets Imported

### ✅ Patients (`patient_data.sql`)
- Personal information (name, DOB, gender, phone, email)
- Medical record numbers (MRN) mapped from legacy PID
- Address and contact information
- **Duplicate Detection**: By MRN, or by name + DOB

### ✅ Drugs (`drugs.sql`)
- Drug names and descriptions
- Pricing (unit_price, cost_price)
- Form (tablet, capsule, injection, etc.)
- Active status
- **Duplicate Detection**: By drug name

### ✅ Services (`codes.sql`)
- Service codes and descriptions
- Categories
- Pricing (fees)
- Active status
- **Note**: Drugs, lab tests, and imaging are excluded (imported separately)

### ✅ Lab Tests (`codes.sql` where is_lab_order=1)
- Test codes and names
- Pricing
- **Duplicate Detection**: By test code

### ✅ Inventory (`drug_inventory.sql`)
- Drug inventory records
- Lot numbers and expiration dates
- Quantities on hand
- Store/warehouse mapping
- **Note**: Requires drug mapping from drugs import

## Database Configuration

### Using PostgreSQL (Default - Recommended)

The system uses your current Django database configuration. Ensure `.env` has:

```bash
DATABASE_URL=postgresql://hms_user:hms_password@localhost:5432/hms_db
```

### Using MySQL

If you want to use MySQL instead:

1. Install MySQL client:
```bash
pip install mysqlclient
# or
pip install pymysql
```

2. Update `.env`:
```bash
DATABASE_URL=mysql://username:password@localhost:3306/hms_db
```

3. Run migrations:
```bash
python manage.py migrate
python manage.py migrate_legacy_data --sql-dir import/db_3_extracted
```

## Duplicate Handling

### Default Behavior: Update Existing

When a duplicate is found, the system:
1. Identifies the existing record
2. Updates it with new data from the import
3. Preserves the original record ID

**Patient Duplicates**:
- By MRN (if exists)
- By first_name + last_name + date_of_birth

**Drug Duplicates**:
- By drug name (case-insensitive)

**Service Duplicates**:
- By service code

**Lab Test Duplicates**:
- By test code

### Skip Duplicates Mode

Use `--skip-duplicates` to skip existing records instead of updating them.

## Progress Tracking

The migration provides real-time progress:
- Shows progress every 100 records for patients and drugs
- Shows progress every 500 records for services
- Displays summary statistics at the end

## Error Handling

- Errors are logged but don't stop the migration
- Up to 10 errors are displayed in the summary
- All errors are logged to Django logging system

## Example Output

```
======================================================================
LEGACY DATA MIGRATION SYSTEM
======================================================================

[1/7] Importing Reference Data...
  Skipping payers/staff (placeholder)

[2/7] Importing Patients...
  Processing import/db_3_extracted/patient_data.sql...
  Processed 100 patients...
  Processed 200 patients...
  ✓ Patients: 1523 created, 45 updated, 12 skipped

[3/7] Importing Drugs/Pharmacy...
  Processing import/db_3_extracted/drugs.sql...
  ✓ Drugs: 2151 created, 0 updated

...

======================================================================
MIGRATION SUMMARY
======================================================================
Patients: 1523 created, 45 updated, 12 skipped
Drugs: 2151 created, 0 updated, 0 skipped
Services: 1843 created, 123 updated, 5 skipped
Lab Tests: 245 created, 12 updated, 0 skipped
Inventory: 3456 records processed
======================================================================
```

## Troubleshooting

### "File not found" errors

Make sure the SQL files are in the correct directory:
```bash
ls import/db_3_extracted/*.sql
```

### "Duplicate key" errors

This usually means data already exists. Use `--update-existing` (default) or `--skip-duplicates`.

### "Foreign key" errors

Make sure dependencies are imported first. The migration handles this automatically, but if you run parts separately, import in order.

### "Character encoding" errors

The migration handles UTF-8 encoding automatically. If you see encoding issues, check the SQL file encoding.

## Advanced Usage

### Import Only Specific Data Types

You can't directly filter by data type in this command, but you can:

1. Run the full migration once
2. Manually delete specific tables
3. Re-run with those SQL files removed

Or modify the command to add `--only-tables` option.

### Custom Field Mapping

To customize field mappings, edit `hospital/management/commands/migrate_legacy_data.py`:

- Update `import_patients()` for patient field mapping
- Update `import_drugs()` for drug field mapping
- And so on...

### Batch Processing

For very large datasets (100K+ records), consider:
1. Running in smaller batches
2. Using database bulk operations
3. Processing outside transaction (remove `@transaction.atomic`)

## Best Practices

1. **Always run dry-run first**: `--dry-run` to preview changes
2. **Backup database**: Before running full migration
3. **Run during off-hours**: Large imports can be time-consuming
4. **Monitor progress**: Watch for errors and adjust as needed
5. **Verify results**: Check counts after migration completes

## Support

For issues or questions:
1. Check error logs in Django logging
2. Review the migration summary statistics
3. Test with `--dry-run` first
4. Verify SQL file format matches expected structure

## Technical Details

### SQL Parsing

The migration uses regex-based SQL parsing to extract INSERT statements from MySQL dump files. It handles:
- Single and multi-row INSERTs
- Quoted strings with escaped quotes
- NULL values
- Boolean values (TRUE/FALSE, 0/1)
- Numbers (integers and decimals)

### Transaction Safety

The entire migration runs in a single transaction:
- If any step fails, all changes are rolled back
- Use `--dry-run` to test without committing
- Remove `@transaction.atomic` decorator for large imports if needed

### Performance

Expected performance:
- **Patients**: ~100-500 records/second
- **Drugs**: ~200-1000 records/second
- **Services**: ~500-2000 records/second
- **Inventory**: ~100-400 records/second

Actual performance depends on:
- Database type (PostgreSQL vs MySQL)
- Hardware (CPU, RAM, disk)
- Network latency (if remote database)
- Existing data volume
