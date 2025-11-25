# 🚀 Quick Start: Database Import

## Import in 3 Easy Steps

### Step 1: Backup Your Database

```bash
copy db.sqlite3 db.sqlite3.backup
```

### Step 2: Run the Import

```bash
python import_database.py
```

Choose option 1 (Import ALL tables) and type `yes` to confirm.

### Step 3: Verify

```bash
python manage.py validate_import
```

---

## That's It! 🎉

Your legacy database is now imported.

## What Got Imported?

✅ **600+ Tables** including:
- Patient records
- Admissions
- Blood Bank
- Laboratory
- Pharmacy
- Insurance
- Accounting
- HR & Staff
- And much more!

## Next Steps

### 1. View the Data

```bash
python manage.py runserver
# Go to http://127.0.0.1:8000/admin/
```

### 2. Check Statistics

```bash
python manage.py validate_import --detailed
```

### 3. Generate Django Models (Optional)

```bash
# For Blood Bank
python manage.py map_legacy_tables --category blood

# For all tables
python manage.py map_legacy_tables --category all
```

## Common Commands

### Import Specific Tables

```bash
# Blood Bank only
python import_database.py
# Choose option 3

# Custom tables
python manage.py import_legacy_database --tables blood_donors blood_stock admissions
```

### Preview Before Import (Dry Run)

```bash
python manage.py import_legacy_database --dry-run
```

### Re-import (if needed)

```bash
# Drop old data first
python manage.py dbshell
DROP TABLE table_name;
.exit

# Then import again
python import_database.py
```

## Troubleshooting

### "Table already exists"
```bash
python manage.py import_legacy_database --skip-drop
```

### "Permission denied"
Make sure the database file is not open in another program.

### Need Help?
Check the full guide: `DATABASE_IMPORT_GUIDE.md`

---

## 📊 Quick Stats Check

After import, run:
```bash
python manage.py validate_import
```

You should see:
- ✅ 600+ tables imported
- ✅ Thousands of rows
- ✅ No integrity issues

## 🎯 What's Available Now

### Blood Bank System
- Donor records
- Blood inventory
- Transfusion tracking

### Clinical Records
- Patient admissions
- Consultation notes
- Prescriptions
- Laboratory results
- Imaging orders

### Administrative
- User accounts
- Billing & invoicing
- Insurance management
- Inventory & pharmacy

### HR & Staff
- Employee records
- Payroll
- Attendance
- Leave management

---

## 💡 Pro Tips

1. **Start with validation**: `python manage.py validate_import`
2. **Check specific categories**: `python manage.py validate_import --detailed`
3. **Generate models gradually**: Start with one category at a time
4. **Keep backups**: Always maintain database backups

---

**Need more details?** See `DATABASE_IMPORT_GUIDE.md`

**Having issues?** Check the troubleshooting section in the full guide




















