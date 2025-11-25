# Database Import Guide

## 🎯 Overview

This system allows you to import all legacy SQL database files from your DS directory into your Hospital Management System.

## 📁 Source Files

- **Location**: `C:\Users\user\Videos\DS\`
- **Total Files**: ~600+ SQL files
- **Database Type**: MySQL format (will be converted to SQLite)

## 🚀 Quick Start

### Method 1: Interactive Script (Recommended)

```bash
python import_database.py
```

This will show you a menu with options:
1. Import ALL tables
2. Import SPECIFIC tables
3. Import Blood Bank tables only
4. DRY RUN (preview)
5. Exit

### Method 2: Django Management Command

```bash
# Import all tables
python manage.py import_legacy_database --skip-drop

# Import specific tables
python manage.py import_legacy_database --tables blood_donors blood_stock

# Dry run (preview only)
python manage.py import_legacy_database --dry-run

# Import from custom directory
python manage.py import_legacy_database --sql-dir "C:\path\to\sql\files"
```

## 📊 Table Categories

### Accounting
- `acc_accounts` - Chart of accounts
- `acc_bills` - Bills and invoices
- `acc_beneficiaries` - Payment beneficiaries
- `acc_chart_accounts` - Account structure
- `acc_currencies` - Currency management
- `acc_invoices` - Customer invoices
- `acc_revenues` - Revenue tracking

### Admissions
- `admissions` - Patient admissions
- `admission_beds` - Bed assignments
- `admission_diagnosis` - Diagnoses
- `admission_drugs` - Medication records
- `admission_fluids` - Fluid charts
- `admission_notes` - Clinical notes
- `admission_prescriptions` - Prescriptions
- `admission_vitals` - Vital signs
- `admission_ward` - Ward information

### Blood Bank
- `blood_donors` - Donor information
- `blood_stock` - Blood inventory

### Clinical Forms
- `form_admission_note` - Admission forms
- `form_consultation_*` - Various consultation forms
- `form_nursing_*` - Nursing documentation
- `form_review_*` - Review forms
- `form_surgery_note` - Surgical notes

### Diagnostics
- `diag_imaging_*` - Radiology/imaging
- `lab_*` - Laboratory system
- `procedure_*` - Procedures

### Insurance
- `insurance_companies` - Insurance providers
- `insurance_numbers` - Policy numbers
- `insurance_price_levels` - Pricing tiers
- `insurance_drug_exclusions` - Drug exclusions
- `insurance_service_exclusions` - Service exclusions

### Patients
- `patient_data` - Patient demographics (if exists)
- `addresses` - Address information
- `phone_numbers` - Contact information

### Pharmacy
- `drugs` - Drug catalog
- `drug_inventory*` - Inventory management
- `drug_sales_*` - Sales records
- `drug_templates` - Prescription templates
- `prices` - Drug pricing

### Staff & HR
- `users` - User accounts
- `users_secure` - Security settings
- `users_facility` - Facility assignments
- `employees` - Employee records
- `attendance` - Attendance tracking
- `payrolls` - Payroll information
- `leaves` - Leave management

### Other Systems
- `bills_*` - Billing
- `packages` - Service packages
- `appointments` (via calendar)
- `prescriptions_*` - Prescriptions
- `immunizations` - Vaccination records

## ⚙️ Import Process

### What Happens During Import

1. **File Discovery**: Scans the SQL directory for .sql files
2. **Conversion**: Converts MySQL syntax to SQLite-compatible syntax
3. **Execution**: Runs CREATE TABLE and INSERT statements
4. **Logging**: Records successes and errors
5. **Summary**: Shows statistics

### SQL Conversions Applied

- `AUTO_INCREMENT` → `AUTOINCREMENT`
- `INT(11)` → `INTEGER`
- `DECIMAL(12,2)` → `REAL`
- `DATETIME` → `TEXT`
- `ENUM(...)` → `TEXT`
- Removes: `ENGINE=InnoDB`, `CHARSET`, `COLLATE`, `KEY` definitions
- Converts: backticks `` to double quotes `""`

## 🛡️ Safety Features

### Skip Drop Tables
The `--skip-drop` flag prevents dropping existing tables, preserving your data.

```bash
python manage.py import_legacy_database --skip-drop
```

### Dry Run
Preview what would be imported without making changes:

```bash
python manage.py import_legacy_database --dry-run
```

## 📝 Step-by-Step Import

### 1. Backup Your Database

```bash
# Copy your database
copy db.sqlite3 db.sqlite3.backup
```

### 2. Run Import

**Option A: Import Everything**
```bash
python import_database.py
# Choose option 1
```

**Option B: Import Blood Bank Only (Example)**
```bash
python import_database.py
# Choose option 3
```

**Option C: Import Specific Tables**
```bash
python manage.py import_legacy_database --tables blood_donors blood_stock admission_beds
```

### 3. Verify Import

```bash
# Check database
python manage.py dbshell

# In SQLite shell:
.tables
SELECT COUNT(*) FROM blood_donors;
.exit
```

### 4. Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Check Admin Interface

```bash
python manage.py runserver
# Visit http://127.0.0.1:8000/admin/
```

## 🔍 Troubleshooting

### Issue: "Table already exists"

**Solution**: Use `--skip-drop` flag or manually drop the table:
```bash
python manage.py dbshell
DROP TABLE table_name;
```

### Issue: "Syntax error near..."

**Cause**: MySQL-specific syntax not converted
**Solution**: Check the logs and report the specific statement

### Issue: "Foreign key constraint failed"

**Solution**: Import parent tables before child tables. The script tries to maintain order, but you may need to import dependencies first.

### Issue: "File not found"

**Solution**: Verify the SQL directory path:
```bash
python manage.py import_legacy_database --sql-dir "C:\Users\user\Videos\DS"
```

## 📊 Monitoring Progress

### View Logs

The import process logs to:
- Console (stdout)
- Django logs (if configured)

### Check Statistics

After import, you'll see:
- Total files processed
- Tables created
- Rows inserted
- Errors encountered

## 🎯 Recommended Import Order

For best results, import in this order:

1. **Reference Data**
   ```bash
   python manage.py import_legacy_database --tables areas currencies
   ```

2. **User & Facility Data**
   ```bash
   python manage.py import_legacy_database --tables users facility addresses
   ```

3. **Medical Records**
   ```bash
   python manage.py import_legacy_database --tables patient_data admissions
   ```

4. **Clinical Data**
   ```bash
   python manage.py import_legacy_database --tables procedures lab_type drugs
   ```

5. **Financial Data**
   ```bash
   python manage.py import_legacy_database --tables acc_accounts prices
   ```

6. **Everything Else**
   ```bash
   python manage.py import_legacy_database
   ```

## 🔗 Integration with Django

### Accessing Legacy Data

After import, you can access the data using Django's ORM:

```python
from django.db import connection

# Query legacy tables
with connection.cursor() as cursor:
    cursor.execute("SELECT * FROM blood_donors LIMIT 10")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
```

### Creating Django Models

To create Django models for legacy tables:

```bash
python manage.py inspectdb blood_donors blood_stock > hospital/models_legacy_blood.py
```

Then edit the file and add to your models.

## 📈 Post-Import Steps

1. **Verify Data Integrity**
   ```bash
   python manage.py check
   ```

2. **Create Indexes** (if needed)
   ```sql
   CREATE INDEX idx_blood_donors_group ON blood_donors(blood_group);
   ```

3. **Update Statistics**
   ```bash
   python manage.py migrate
   ```

4. **Test Queries**
   - Check admin interface
   - Run sample queries
   - Verify relationships

## 💡 Tips

1. **Start Small**: Import a few tables first to test
2. **Use Dry Run**: Always preview before full import
3. **Backup First**: Always backup your database
4. **Check Logs**: Review logs for any warnings
5. **Verify Data**: Spot-check imported data in admin

## 🆘 Support

If you encounter issues:

1. Check the error message carefully
2. Review the troubleshooting section
3. Check Django logs
4. Verify SQL file format
5. Test with a single table first

## 📚 Additional Resources

- Django Database Documentation: https://docs.djangoproject.com/en/5.1/topics/db/
- SQLite Documentation: https://www.sqlite.org/docs.html
- MySQL to SQLite Migration: Various online tools available

## ✅ Success Checklist

- [ ] Database backed up
- [ ] SQL directory verified
- [ ] Django settings configured
- [ ] Import script run successfully
- [ ] Data verified in database
- [ ] Django migrations run
- [ ] Admin interface checked
- [ ] Sample queries tested

---

**Last Updated**: November 2025
**Version**: 1.0




















