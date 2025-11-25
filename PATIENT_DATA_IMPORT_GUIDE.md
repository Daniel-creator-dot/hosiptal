# 🏥 Patient Data Import Guide

## Problem: Can't See Patient Tables

You have patient-related SQL files but they haven't been imported yet.

---

## ✅ Solution: Import Patient Data (3 Methods)

### Method 1: One-Click Import (Easiest!)

**Just double-click this file:**
```
IMPORT_PATIENT_DATA_NOW.bat
```

That's it! The patient tables will be imported.

---

### Method 2: Command Line

```bash
python manage.py import_legacy_database --tables patient_data patient_reminders patient_tracker patient_tracker_element patient_access_onsite patient_access_offsite patient_portal_menu --skip-drop
```

---

### Method 3: Interactive Import

```bash
python import_database.py
```

Then choose option 2 (Import SPECIFIC tables) and enter:
```
patient_data patient_reminders patient_tracker
```

---

## 📊 What Gets Imported

The following patient-related tables will be imported:

1. **`patient_data`** - Main patient demographics and records
   - Patient names, DOB, contact info
   - Medical history
   - Insurance information

2. **`patient_reminders`** - Patient appointment reminders

3. **`patient_tracker`** - Patient tracking/monitoring

4. **`patient_tracker_element`** - Tracking elements

5. **`patient_access_onsite`** - Onsite access records

6. **`patient_access_offsite`** - Offsite/portal access

7. **`patient_portal_menu`** - Patient portal menu items

---

## 🔍 Verify Import Was Successful

### Check 1: Count Records

```bash
python manage.py dbshell
```

Then in SQLite:
```sql
SELECT COUNT(*) FROM patient_data;
```

You should see a number > 0.

### Check 2: View Sample Data

```sql
SELECT * FROM patient_data LIMIT 5;
```

### Check 3: List All Patient Tables

```sql
SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%patient%';
```

Type `.exit` to leave SQLite shell.

---

## 🎯 Quick Commands

```bash
# Import patient data
IMPORT_PATIENT_DATA_NOW.bat

# OR use Python
python manage.py import_legacy_database --tables patient_data --skip-drop

# Verify
python manage.py validate_import

# Check specific table
python manage.py dbshell
SELECT COUNT(*) FROM patient_data;
.exit
```

---

## 📝 Important Notes

### Django Patient Model vs Legacy patient_data

Your Django app has a `Patient` model (in `hospital/models.py`), but the legacy database has a `patient_data` table with a **different structure**.

**Two options:**

#### Option 1: Use Legacy Data Directly
```python
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("SELECT * FROM patient_data LIMIT 10")
    patients = cursor.fetchall()
    for patient in patients:
        print(patient)
```

#### Option 2: Migrate to Django Model

Generate a model for the legacy table:
```bash
python manage.py map_legacy_tables --tables patient_data --output hospital/models_legacy_patient.py
```

Then edit the file to match your needs.

---

## 🔧 Troubleshooting

### "Table already exists"
```bash
# Use skip-drop flag
python manage.py import_legacy_database --tables patient_data --skip-drop
```

### "No such table: patient_data"
```bash
# Import hasn't been run yet, run the import:
IMPORT_PATIENT_DATA_NOW.bat
```

### "Empty table"
Check if the SQL file has data:
- Look at: `C:\Users\user\Videos\DS\patient_data.sql`
- Should have INSERT statements

---

## 📊 After Import

### View Data in Admin

1. Generate model:
```bash
python manage.py inspectdb patient_data > temp_patient_model.py
```

2. Copy the model to `hospital/models.py`

3. Register in `hospital/admin.py`:
```python
from django.contrib import admin
from .models import PatientData  # or whatever you named it

@admin.register(PatientData)
class PatientDataAdmin(admin.ModelAdmin):
    list_display = ['id', 'fname', 'lname', 'DOB']
    search_fields = ['fname', 'lname']
```

4. Run migrations:
```bash
python manage.py makemigrations
python manage.py migrate
```

5. View in admin:
```bash
python manage.py runserver
# Visit: http://127.0.0.1:8000/admin/
```

---

## 🚀 Quick Start Checklist

- [ ] Double-click `IMPORT_PATIENT_DATA_NOW.bat`
- [ ] Wait for import to complete (1-5 minutes)
- [ ] Run: `python manage.py validate_import`
- [ ] Check: `python manage.py dbshell` then `SELECT COUNT(*) FROM patient_data;`
- [ ] Verify: Data shows in queries
- [ ] Optional: Generate Django models
- [ ] Optional: Register in admin

---

## 💡 Pro Tips

1. **Start with patient_data** - It's the main table
2. **Check the count** - Should have thousands of records
3. **Sample the data** - Use LIMIT 5 to see structure
4. **Generate models** - Use inspectdb for Django integration
5. **Keep legacy structure** - Don't modify SQL files

---

## 📞 Need Help?

If patient data still doesn't show:

1. Check SQL files exist:
   - Location: `C:\Users\user\Videos\DS\`
   - Look for: `patient_data.sql`

2. Check file contents:
   - Open the file in a text editor
   - Should have CREATE TABLE and INSERT statements

3. Try importing manually:
   ```bash
   python manage.py dbshell < C:\Users\user\Videos\DS\patient_data.sql
   ```

4. Check for errors:
   ```bash
   python manage.py validate_import --check-integrity
   ```

---

## ✅ Success Criteria

You'll know it worked when:

✓ `SELECT COUNT(*) FROM patient_data;` returns > 0
✓ `SELECT * FROM patient_data LIMIT 5;` shows records
✓ No error messages during import
✓ `validate_import` shows patient tables

---

**Ready?** Double-click: `IMPORT_PATIENT_DATA_NOW.bat`

Or run: `python manage.py import_legacy_database --tables patient_data --skip-drop`

---

*Last Updated: November 2025*




















