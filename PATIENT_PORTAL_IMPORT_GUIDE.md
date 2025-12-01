# Patient Portal Data Import Guide

## Overview

This guide explains how to import patient portal data from SQL files and automatically create Patient records with QR codes.

## Files Imported

1. **patient_portal_menu.sql** - Portal menu configuration
2. **patient_reminders.sql** - Patient reminder records
3. **patient_access_offsite.sql** - Offsite portal access credentials
4. **patient_access_onsite.sql** - Onsite portal access credentials

## What This Import Does

1. ✅ **Creates table structures** - Imports the table definitions
2. ✅ **Imports data** - If INSERT statements exist in SQL files
3. ✅ **Extracts patient IDs** - Finds all unique PIDs from access tables
4. ✅ **Creates Patient records** - Creates Patient records for each PID
5. ✅ **Generates QR codes** - Automatically creates QR codes for all patients

## Quick Start

### Option 1: Using Batch File (Windows)

1. Place your SQL files in `f:\` directory:
   - `f:\patient_portal_menu.sql`
   - `f:\patient_reminders.sql`
   - `f:\patient_access_offsite.sql`
   - `f:\patient_access_onsite.sql`

2. Run the import:
   ```bash
   IMPORT_PATIENT_PORTAL.bat
   ```

### Option 2: Using Docker Command

```bash
docker-compose exec web python manage.py import_patient_portal_data --sql-dir f:\
```

### Option 3: Custom Directory

If your SQL files are in a different location:

```bash
docker-compose exec web python manage.py import_patient_portal_data --sql-dir "C:\path\to\sql\files"
```

## Command Options

### Dry Run (Test Without Importing)

```bash
docker-compose exec web python manage.py import_patient_portal_data --sql-dir f:\ --dry-run
```

This will show you what would be imported without actually importing.

### Skip Patient Creation

```bash
docker-compose exec web python manage.py import_patient_portal_data --sql-dir f:\ --no-create-patients
```

This will only import the table structures and data, but won't create Patient records.

## How It Works

### Step 1: Import Table Structures

The script reads each SQL file and:
- Converts MySQL syntax to PostgreSQL
- Creates the table structure
- Imports any INSERT data if present

### Step 2: Extract Patient IDs

The script queries the imported tables to find all unique `pid` values:
- From `patient_access_offsite`
- From `patient_access_onsite`
- From `patient_reminders`

### Step 3: Create Patient Records

For each unique PID found:
1. Checks if a Patient record already exists (by MRN: `PMC-LEG-{PID}`)
2. If not, creates a new Patient record with:
   - MRN: `PMC-LEG-{PID}` (e.g., `PMC-LEG-000123`)
   - Basic placeholder data (can be updated later)
3. Automatically generates a QR code via Django signal

## Patient MRN Format

Patients are created with MRNs in the format:
```
PMC-LEG-{PID}
```

Example:
- PID 123 → MRN: `PMC-LEG-000123`
- PID 4567 → MRN: `PMC-LEG-004567`

## QR Code Generation

QR codes are **automatically generated** for all patients via Django signals. Each patient gets:
- ✅ Unique QR token
- ✅ QR code image
- ✅ QR code data (patient UUID)

### View QR Codes

After import, view QR codes:
1. Go to: `http://localhost:8000/hms/patients/`
2. Click on any patient
3. Click "QR Card" button
4. Download or print the QR code

## Updating Patient Details

After import, you may want to update patient details from the `patient_data` table:

1. **If you have patient_data table:**
   ```bash
   docker-compose exec web python manage.py import_legacy_patients --sql-dir f:\
   ```

2. **Or manually update in Django Admin:**
   - Go to: `http://localhost:8000/admin/hospital/patient/`
   - Edit each patient's details

## Troubleshooting

### "Table already exists"

This is normal if you've run the import before. The script will skip creating existing tables.

### "No SQL files found"

Make sure your SQL files are in the correct directory:
- Default: `f:\`
- Or specify with `--sql-dir` option

### "No PIDs found"

This means:
- The tables were created but have no data
- Or the SQL files only contain CREATE TABLE statements (no INSERT data)

**Solution:** If you have data files with INSERT statements, add them to the SQL files or import them separately.

### "Error creating patient"

This usually means:
- Database connection issue
- Constraint violation (e.g., duplicate MRN)

**Solution:** Check the error message and ensure:
- Docker is running
- Database is accessible
- No duplicate MRNs exist

## Expected Output

```
============================================================
PATIENT PORTAL DATA IMPORT
============================================================

[1/3] Importing table structures and data...
  ✅ patient_portal_menu (structure only)
  ✅ patient_reminders (structure + 150 rows)
  ✅ patient_access_offsite (structure + 45 rows)
  ✅ patient_access_onsite (structure + 30 rows)
  Total rows imported: 225

[2/3] Extracting patient IDs from access tables...
  Found 45 PIDs in patient_access_offsite
  Found 30 PIDs in patient_access_onsite
  Found 150 PIDs in patient_reminders
  Total unique PIDs found: 180

[3/3] Creating Patient records with QR codes...
  Progress: 10 patients created...
  Progress: 20 patients created...
  ...

============================================================
IMPORT SUMMARY
============================================================
  Tables imported: 4
  Unique PIDs found: 180
  Patients created: 180
  Patients updated: 0
  QR codes generated: 180
  Skipped: 0

✅ All patients now have QR codes!

Import completed!
```

## Next Steps

1. ✅ **Verify patients were created:**
   ```bash
   docker-compose exec web python manage.py shell -c "from hospital.models import Patient; print(f'Total patients: {Patient.objects.filter(is_deleted=False).count()}')"
   ```

2. ✅ **Verify QR codes exist:**
   ```bash
   docker-compose exec web python manage.py shell -c "from hospital.models import PatientQRCode; print(f'QR codes: {PatientQRCode.objects.count()}')"
   ```

3. ✅ **View in web interface:**
   - Patients: `http://localhost:8000/hms/patients/`
   - QR Cards: Click any patient → "QR Card"

4. ✅ **Update patient details** from `patient_data` if available

## Files Created

- `hospital/management/commands/import_patient_portal_data.py` - Import command
- `IMPORT_PATIENT_PORTAL.bat` - Windows batch file for easy import
- `PATIENT_PORTAL_IMPORT_GUIDE.md` - This guide





