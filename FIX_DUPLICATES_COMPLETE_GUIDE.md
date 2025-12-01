# Complete Guide to Fix Database Duplicates

## Problem
The system is creating duplicate patients and staff immediately after registration. This is happening because:
1. Multiple database files exist (SQLite backups + main database)
2. Import scripts may not check for duplicates
3. Race conditions in registration (already fixed in code)
4. Existing duplicates in the database need to be cleaned up

## Solution - Step by Step

### Step 1: Check Database Configuration

Run this command to see which database is being used:
```bash
python manage.py shell -c "from django.conf import settings; print('Database:', settings.DATABASES['default'])"
```

**IMPORTANT**: Ensure only ONE database is configured in your `.env` file:
```
DATABASE_URL=postgresql://user:pass@localhost:5432/hms_db
```
OR
```
DATABASE_URL=mysql://user:pass@localhost:3306/hms_db
```

**DO NOT** use SQLite in production - it causes concurrency issues.

### Step 2: Find Existing Duplicates

Run the duplicate detection command:
```bash
python manage.py fix_duplicates --dry-run
```

This will show you:
- How many duplicate patients exist
- How many duplicate staff exist
- Details of each duplicate set

### Step 3: Fix Existing Duplicates

Once you've reviewed the duplicates, fix them:
```bash
python manage.py fix_duplicates --fix
```

This will:
- Keep the oldest record (first created)
- Merge data from duplicates into the primary record
- Mark duplicates as deleted (soft delete)
- Preserve all relationships

### Step 4: Verify Only One Database

Check for multiple database files:
```bash
# Windows PowerShell
Get-ChildItem -Recurse -Filter "*.sqlite3" | Select-Object FullName
Get-ChildItem -Recurse -Filter "*.db" | Select-Object FullName
```

**If you find multiple SQLite files:**
1. Identify which one is the active database (check settings.py)
2. Backup the others
3. Delete or move unused database files to `backups/` folder
4. Ensure `.env` file points to only ONE database

### Step 5: Check Import Scripts

All import scripts should check for duplicates before creating records. The following scripts have been identified:

**Patient Import Scripts:**
- `hospital/management/commands/import_legacy_patients.py`
- `hospital/management/commands/migrate_legacy_to_django.py`
- `hospital/management/commands/bulk_migrate_legacy.py`
- `import_patient_final.py`
- `restore_staff_and_patients.py`

**Staff Import Scripts:**
- `hospital/management/commands/import_staff.py`
- `restore_staff_and_patients.py`
- `create_specialists.py`

**Action Required**: Review these scripts and ensure they:
1. Check for existing records before creating
2. Use `get_or_create()` instead of `create()`
3. Handle duplicate errors gracefully

### Step 6: Prevent Future Duplicates

The following fixes are already in place:

✅ **Form Validation** - `PatientForm.clean()` and `StaffForm.clean()` check for duplicates
✅ **View Validation** - Duplicate checks inside transactions
✅ **JavaScript** - Prevents double-submission
✅ **Database Constraints** - Unique constraints on MRN, national_id, employee_id, username, email

### Step 7: Monitor for Duplicates

Set up a periodic check:
```bash
# Add to cron or scheduled task
python manage.py fix_duplicates --dry-run
```

## Quick Fix Commands

### Check for duplicates (no changes):
```bash
python manage.py fix_duplicates --dry-run
```

### Fix patient duplicates only:
```bash
python manage.py fix_duplicates --fix --patients-only
```

### Fix staff duplicates only:
```bash
python manage.py fix_duplicates --fix --staff-only
```

### Fix all duplicates:
```bash
python manage.py fix_duplicates --fix
```

## What the Fix Does

1. **Finds Duplicates By:**
   - Patients: Name + DOB + Phone, Email, National ID
   - Staff: Username, Email, Employee ID

2. **Merges Duplicates:**
   - Keeps the oldest record (first created)
   - Merges missing data from duplicates
   - Preserves all relationships (encounters, invoices, etc.)
   - Soft deletes duplicates (marks as `is_deleted=True`)

3. **Reports:**
   - Shows all duplicate sets found
   - Shows which records are kept vs merged
   - Provides summary statistics

## Database Configuration

### Ensure Single Database

**Check current database:**
```python
# In Django shell
from django.conf import settings
print(settings.DATABASES['default'])
```

**Verify .env file:**
- Should have only ONE `DATABASE_URL` line
- Should point to your production database
- Should NOT use SQLite in production

**If using PostgreSQL:**
```
DATABASE_URL=postgresql://hms_user:hms_password@localhost:5432/hms_db
```

**If using MySQL:**
```
DATABASE_URL=mysql://hms_user:hms_password@localhost:3306/hms_db
```

## Troubleshooting

### "No duplicates found" but you see duplicates
- Check if duplicates are marked as `is_deleted=True`
- Run: `Patient.objects.filter(is_deleted=False).count()`
- Check if using different database than expected

### "Database locked" errors
- SQLite doesn't handle concurrent access well
- Switch to PostgreSQL or MySQL
- If must use SQLite, ensure only one process accesses it

### Duplicates keep appearing
- Check all import scripts for duplicate checking
- Verify form validation is working
- Check browser console for JavaScript errors
- Verify database constraints are in place

## Files Modified/Created

1. ✅ `hospital/management/commands/fix_duplicates.py` - New command to find and fix duplicates
2. ✅ `hospital/forms.py` - Added duplicate checking in PatientForm
3. ✅ `hospital/forms_hr.py` - Added duplicate checking in StaffForm
4. ✅ `hospital/views.py` - Moved duplicate checks inside transaction
5. ✅ `hospital/templates/hospital/patient_form.html` - Added double-submission prevention

## Next Steps

1. **Immediate**: Run `python manage.py fix_duplicates --dry-run` to see current state
2. **Fix**: Run `python manage.py fix_duplicates --fix` to clean up duplicates
3. **Verify**: Check database configuration ensures single database
4. **Monitor**: Set up periodic duplicate checks
5. **Review**: Check all import scripts for duplicate prevention

## Support

If duplicates persist:
1. Check database logs for errors
2. Verify only one database is configured
3. Check import script logs
4. Review form submission logs
5. Check for JavaScript errors in browser console

