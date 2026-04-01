# 💰 Import Consultation Prices - Docker Instructions

## 🎯 Quick Start (Docker)

### Option 1: Run via Docker Exec (Recommended)

```bash
# Step 1: Find your container name
docker ps

# Step 2: Run the import command
docker exec -it <container_name> python manage.py import_consultation_prices --verbose

# Example:
docker exec -it hms-web-1 python manage.py import_consultation_prices --verbose
```

### Option 2: Run via Docker Compose

```bash
# If using docker-compose
docker-compose exec web python manage.py import_consultation_prices --verbose
```

### Option 3: Run in Interactive Shell

```bash
# Enter the container
docker exec -it <container_name> bash

# Then run the command
python manage.py import_consultation_prices --verbose
```

---

## 📋 Step-by-Step Guide

### Step 1: Verify Excel File Location

The import command looks for the file at:
```
hms/prices/Consult Price List 2025(1).xlsx
```

If your file is in a different location, use:
```bash
docker exec -it <container_name> python manage.py import_consultation_prices --file "path/to/your/file.xlsx" --verbose
```

### Step 2: Test with Dry Run (Optional)

```bash
docker exec -it <container_name> python manage.py import_consultation_prices --dry-run --verbose
```

This validates the file without saving to database.

### Step 3: Run Actual Import

```bash
docker exec -it <container_name> python manage.py import_consultation_prices --verbose
```

---

## ✅ Expected Output

```
================================================================================
PROFESSIONAL CONSULTATION PRICE IMPORT SYSTEM
================================================================================

Loading Excel file: hms/prices/Consult Price List 2025(1).xlsx
✓ File loaded successfully

Analyzing file structure...
✓ Found 26 columns
  Cash column: 23
  Corporate column: 10
  Insurance column: 16
  Insurance companies: 15

Setting up pricing categories...
  ✓ Created category: Cash / Private Patients
  ✓ Created category: Corporate / Company
  ✓ Created category: Insurance (General)
  ✓ Created category: Insurance - ACE
  ✓ Created category: Insurance - GLICO
  ... (more categories)

Processing consultation prices...
  Processed 50 services...
  Processed 100 services...
  ... (progress updates)

================================================================================
IMPORT SUMMARY
================================================================================
  Services processed: 1,549
  Services created: 1,549
  Services updated: 0
  Prices created: 4,647
  Prices updated: 0
  Errors: 0

✓ Import completed successfully!

You can now view prices at: /hms/pricing/
```

---

## 🔍 Verify Import

### 1. Check Pricing Dashboard
```
http://localhost:8000/hms/pricing/
```

### 2. Check Django Admin
```
http://localhost:8000/admin/hospital/serviceprice/
```

### 3. Check Price Matrix
```
http://localhost:8000/hms/pricing/matrix/
```

---

## 🛠️ Troubleshooting

### File Not Found
```
ERROR: File not found: hms/prices/Consult Price List 2025(1).xlsx
```

**Solution:**
1. Copy file into container:
   ```bash
   docker cp "Consult Price List 2025(1).xlsx" <container_name>:/app/hms/prices/
   ```

2. Or use custom path:
   ```bash
   docker exec -it <container_name> python manage.py import_consultation_prices --file "/app/path/to/file.xlsx"
   ```

### Container Not Running
```
Error: No such container
```

**Solution:**
```bash
# Start containers
docker-compose up -d

# Or
docker start <container_name>
```

### Database Connection Error
```
django.core.exceptions.ImproperlyConfigured: Error loading psycopg2
```

**Solution:** This should not happen in Docker. If it does, restart the container:
```bash
docker-compose restart
```

---

## 📊 What Gets Imported

### Services Created
- All consultation types from Excel
- Format: "{SpecialistType} - {VisitType}"
- Example: "ANTENATAL CONSULTATION - First Consultation"

### Pricing Categories Created
- Cash / Private Patients
- Corporate / Company
- Insurance (General)
- Individual insurance companies (ACE, GLICO, GRIDCO, etc.)

### Prices Imported
- Cash prices → Cash category
- Corporate prices → Corporate category
- Insurance prices → Insurance category
- Individual insurance company prices → Specific categories

---

## 🎯 After Import

### View Prices
1. Navigate to: `http://localhost:8000/hms/pricing/`
2. Click on any pricing category
3. See all imported consultation prices

### Use in Billing
- Prices automatically appear when billing
- System selects correct price based on patient type
- All price types (Cash, Corporate, Insurance) work

---

## 🔄 Re-importing

If you need to re-import (e.g., after updating Excel):

```bash
# The command will update existing prices
docker exec -it <container_name> python manage.py import_consultation_prices --verbose
```

Existing prices will be updated, new ones will be created.

---

**Status:** ✅ Ready for Production  
**Last Updated:** 2025-12-29








