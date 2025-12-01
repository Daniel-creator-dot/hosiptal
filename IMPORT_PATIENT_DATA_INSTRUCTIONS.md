# 📋 Import Patient Data Instructions

## Current Status

✅ **Found**: `import/legacy/patient_data.sql` (16.14 MB, ~35,000 patient records)  
⚠️ **Database**: Empty (0 patients)  
🎯 **Goal**: Import patient data into PostgreSQL

---

## 🚀 Import Methods

### Method 1: Using Django Management Command (Recommended)

**Run this command and let it complete (may take 5-10 minutes):**

```bash
docker-compose exec web python manage.py import_legacy_database --tables patient_data --sql-dir import/legacy --skip-drop
```

**Important**: 
- ⏱️ This will take **5-10 minutes** - DO NOT cancel it!
- The command processes ~35,000 SQL statements
- You'll see progress messages as it runs

---

### Method 2: Direct PostgreSQL Import (Faster)

If Method 1 doesn't work, use PostgreSQL's `psql` directly:

```bash
# Copy SQL file into container
docker cp import/legacy/patient_data.sql $(docker-compose ps -q web):/tmp/patient_data.sql

# Import using psql
docker-compose exec db psql -U hms_user -d hms_db -f /tmp/patient_data.sql
```

**Note**: This requires the SQL file to be PostgreSQL-compatible. If it's MySQL format, Method 1 is better.

---

### Method 3: Manual Import via Django Shell

```bash
docker-compose exec web python manage.py shell
```

Then in the shell:
```python
from django.db import connection
import os

sql_file = 'import/legacy/patient_data.sql'
with open(sql_file, 'r') as f:
    sql = f.read()

# Convert and execute (simplified)
with connection.cursor() as cursor:
    # Execute in chunks
    for statement in sql.split(';'):
        if statement.strip():
            try:
                cursor.execute(statement)
            except Exception as e:
                print(f"Error: {e}")
```

---

## ✅ After Import - Verification

Once import completes, verify it worked:

```bash
docker-compose exec web python manage.py check_patient_database
```

You should see:
```
✅ Total Legacy Patients: 35,000+ patients
```

---

## 🎯 View Patients in UI

After successful import:

1. **Go to**: http://127.0.0.1:8000/hms/patients/
2. **Use Source Filter**: Select "Imported Legacy" from the dropdown
3. **Click Search**: You should see all imported patients!

---

## ⚠️ Troubleshooting

### "Table already exists"
- The table was partially imported
- Drop it first: `docker-compose exec web python manage.py dbshell`
- Then: `DROP TABLE patient_data;` and `.exit`
- Run import again

### "Syntax error"
- The SQL file might be MySQL format
- Use Method 1 (Django command handles conversion)

### Import is slow
- This is normal! 35,000 records takes time
- Be patient and let it complete

### Import was canceled
- Restart the import command
- It will skip already imported records if using `--skip-drop`

---

## 📊 Expected Results

After successful import:
- ✅ `patient_data` table created in PostgreSQL
- ✅ ~35,000 patient records imported
- ✅ Patients visible in UI with "Source: Legacy" filter
- ✅ Can search and view patient details

---

## 🆘 Need Help?

If import fails:
1. Check Docker logs: `docker-compose logs web`
2. Verify file exists: `docker-compose exec web ls -lh /app/import/legacy/patient_data.sql`
3. Check database connection: `docker-compose exec web python manage.py check_patient_database`


