# 💰 Professional Consultation Price Import Guide

## 🎯 Overview

This professional-grade import system imports all consultation prices from your Excel file into the database, making them visible in Docker Desktop and throughout your HMS system.

---

## 🚀 Quick Start

### Step 1: Run the Import Command

```bash
# Basic import (recommended)
python manage.py import_consultation_prices

# With verbose output (see detailed progress)
python manage.py import_consultation_prices --verbose

# Dry run (validate without saving)
python manage.py import_consultation_prices --dry-run

# Custom file path
python manage.py import_consultation_prices --file "path/to/your/file.xlsx"
```

---

## ✨ What It Does

### 1. **Automatically Creates Pricing Categories**
- ✅ Cash / Private Patients
- ✅ Corporate / Company
- ✅ Insurance (General)
- ✅ Individual Insurance Companies (ACE, GLICO, GRIDCO, etc.)

### 2. **Creates Service Codes**
- ✅ Generates unique service codes for each consultation type
- ✅ Formats: `{SpecialistType} - {VisitType}`
- ✅ Example: "ANTENATAL CONSULTATION - First Consultation"

### 3. **Imports All Prices**
- ✅ Cash prices → Cash category
- ✅ Corporate prices → Corporate category
- ✅ Insurance prices → Insurance category
- ✅ Individual insurance company prices → Specific insurance categories

---

## 📊 Import Statistics

After running, you'll see:

```
================================================================================
IMPORT SUMMARY
================================================================================
  Services processed: 1,549
  Services created: 1,549
  Services updated: 0
  Prices created: 4,647
  Prices updated: 0
  Errors: 0
```

---

## 🔍 Verification

### Check in Django Admin:
```
URL: http://127.0.0.1:8000/admin/hospital/servicecode/
URL: http://127.0.0.1:8000/admin/hospital/pricingcategory/
URL: http://127.0.0.1:8000/admin/hospital/serviceprice/
```

### Check in Pricing Dashboard:
```
URL: http://127.0.0.1:8000/hms/pricing/
```

### Check Price Matrix:
```
URL: http://127.0.0.1:8000/hms/pricing/matrix/
```

---

## 🎨 Features

### ✅ Professional Error Handling
- Validates file before processing
- Skips invalid rows gracefully
- Reports all errors clearly

### ✅ Transaction Safety
- All-or-nothing import (database transaction)
- Rollback on critical errors
- Data integrity guaranteed

### ✅ Progress Reporting
- Real-time progress updates
- Detailed statistics
- Error reporting

### ✅ Dry Run Mode
- Validate file without saving
- Check for errors before import
- Preview what will be imported

### ✅ Smart Service Code Generation
- Auto-generates codes if missing
- Updates existing services
- Maintains consistency

---

## 📋 Excel File Format

The system expects:

| Column | Description |
|--------|-------------|
| SpecialistTypeID | Service code (optional) |
| SpecialistTypeName | Consultation type name |
| Visit Type | Visit type (First, Subsequent, etc.) |
| [I100] cash / 100 Percent Mark-up | Cash price |
| [I102] other COMPANY(coperate) | Corporate price |
| [I103] INSURANCE | Insurance price |
| [I002] ACE | Insurance company prices |
| ... | Other insurance companies |

---

## 🔧 Advanced Usage

### Import with Custom File:
```bash
python manage.py import_consultation_prices --file "hms/prices/Consult Price List 2025(1).xlsx" --verbose
```

### Validate Before Import:
```bash
# Step 1: Dry run
python manage.py import_consultation_prices --dry-run --verbose

# Step 2: If validation passes, run actual import
python manage.py import_consultation_prices --verbose
```

---

## 🎯 After Import

### View Prices:
1. Go to: `http://127.0.0.1:8000/hms/pricing/`
2. Click on any pricing category
3. See all imported prices

### Use in Billing:
- Prices automatically appear when billing patients
- System selects correct price based on patient type
- Cash, Corporate, and Insurance prices all work

---

## ⚠️ Troubleshooting

### File Not Found:
```
ERROR: File not found: hms/prices/Consult Price List 2025(1).xlsx
```
**Solution:** Check file path or use `--file` option

### No Header Row Found:
```
ERROR: Could not find header row
```
**Solution:** Ensure Excel file has header row with "cash" in one of the columns

### Import Errors:
- Check error messages in output
- Verify Excel file format
- Ensure database is accessible

---

## 📞 Support

If you encounter issues:
1. Run with `--verbose` flag for detailed output
2. Run with `--dry-run` to validate first
3. Check error messages in the output

---

## ✅ Success Indicators

You'll know it worked when:
- ✅ No errors in output
- ✅ Services appear in admin
- ✅ Prices visible in pricing dashboard
- ✅ Can select prices when billing

---

**Status:** ✅ Production Ready  
**Last Updated:** 2025-12-29








