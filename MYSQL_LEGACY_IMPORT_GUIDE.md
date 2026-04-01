# MySQL Legacy Data Import Guide

## ✅ Setup Complete!

Your system is now configured to import legacy data from MySQL into Django PostgreSQL.

## 📋 What Was Configured

### 1. **MySQL Container (db_2)**
- Added to `docker-compose.yml`
- Image: `mysql:8.0`
- Database: `legacy_db`
- User: `legacy_user` / Password: `legacy_password`
- Port: `3306`
- Automatically loads SQL files from `import/` folder on startup

### 2. **Import Command**
- Location: `hospital/management/commands/import_mysql_legacy.py`
- Imports: Patients, Encounters, Diagnoses, Prescriptions, Lab Results, Notes

## 🚀 How to Use

### **Start MySQL Container**
```bash
docker compose up -d db_2
```

### **Run Import Command**

**Dry Run (Test without importing):**
```bash
python manage.py import_mysql_legacy --dry-run --limit 10
```

**Import Limited Records (Testing):**
```bash
python manage.py import_mysql_legacy --limit 100
```

**Import All Data:**
```bash
python manage.py import_mysql_legacy
```

**Import Only Patients:**
```bash
python manage.py import_mysql_legacy --patients-only
```

**Import Only Encounters:**
```bash
python manage.py import_mysql_legacy --encounters-only
```

## 📊 What Gets Imported

### **1. Patients** (`patient_data` table)
- Maps: `fname` → `first_name`, `lname` → `last_name`, `mname` → `middle_name`
- Maps: `DOB` → `date_of_birth`, `sex` → `gender`
- Maps: `phone_cell/phone_home` → `phone_number`
- Maps: `pid` → `mrn` (format: `MRN000001`)
- Creates unique MRN for each patient

### **2. Encounters** (`form_encounter`, `external_encounters`, `issue_encounter`)
- Maps encounter types: outpatient, inpatient, emergency, surgery
- Links to imported patients
- Preserves dates, chief complaints, diagnoses, notes

### **3. Diagnoses** (`form_diagnosis`, `visit_diagnosis`, `admission_diagnosis`)
- Stores in encounter `diagnosis` field
- Links to patient and encounter

### **4. Prescriptions** (`prescriptions`, `form_consultation_prescriptions`)
- Creates Drug records if they don't exist
- Creates Order records
- Creates Prescription records with dosage, frequency, duration

### **5. Lab Results** (`lab_result`, `lab_report`, `form_consultation_laboratory`)
- Creates LabTest records if they don't exist
- Creates Order records
- Creates LabResult records with values, units, ranges

### **6. Notes** (`notes`, `form_note`, `form_nurse_note`, `form_consultation`)
- Appends to encounter `notes` field
- Preserves timestamps and content

## 🔍 Data Mapping

### **Patient Fields:**
| MySQL Field | Django Field | Notes |
|------------|--------------|-------|
| `pid` | `mrn` | Generated as `MRN{pid:06d}` |
| `fname` | `first_name` | Max 100 chars |
| `lname` | `last_name` | Max 100 chars |
| `mname` | `middle_name` | Max 100 chars |
| `DOB` | `date_of_birth` | Parsed safely |
| `sex` | `gender` | M/F/O normalized |
| `phone_cell` / `phone_home` | `phone_number` | Normalized to +233 format |
| `email` / `email_direct` | `email` | Max 254 chars |
| `street` + `city` + `state` | `address` | Combined |
| `ss` / `drivers_license` | `national_id` | Max 20 chars |

### **Encounter Fields:**
| MySQL Field | Django Field | Notes |
|------------|--------------|-------|
| `pid` | `patient` | Linked via patient_map |
| `encounter_type` / `type` | `encounter_type` | Mapped: outpatient/inpatient/er/surgery |
| `date` / `encounter_date` | `started_at` | Parsed to datetime |
| `end_date` / `ended_at` | `ended_at` | Optional |
| `chief_complaint` / `complaint` | `chief_complaint` | Max 500 chars |
| `diagnosis` | `diagnosis` | Max 500 chars |
| `notes` | `notes` | Max 1000 chars |

## ⚙️ Configuration

### **MySQL Connection Settings:**
- Host: `localhost` (or `db_2` from Docker)
- Port: `3306`
- Database: `legacy_db`
- User: `legacy_user`
- Password: `legacy_password`

### **SQL Files Location:**
- Extracted from: `import/db_2.zip`
- Location: `import/*.sql`
- Automatically loaded by MySQL container on first startup

## 📝 Import Process

1. **Connects to MySQL** (`db_2` container)
2. **Imports Patients** first (required for other imports)
3. **Imports Encounters** (links to patients)
4. **Imports Diagnoses** (links to encounters)
5. **Imports Prescriptions** (creates drugs/orders as needed)
6. **Imports Lab Results** (creates tests/orders as needed)
7. **Imports Notes** (appends to encounters)

## 🔧 Troubleshooting

### **"Failed to connect to MySQL"**
- Check if container is running: `docker compose ps db_2`
- Start container: `docker compose up -d db_2`
- Wait 30 seconds for MySQL to initialize

### **"No tables found"**
- SQL files should auto-load on container startup
- Check: `docker compose exec db_2 mysql -u legacy_user -plegacy_password legacy_db -e "SHOW TABLES;"`
- If empty, manually load: Copy SQL files to container and import

### **"Import failed: ..."**
- Check error message for specific issue
- Common issues:
  - Missing required fields
  - Invalid date formats
  - Foreign key constraints
- Run with `--limit 10` to test small batches first

### **"UnicodeEncodeError"**
- Fixed in latest version (replaced special characters)
- If persists, set environment: `PYTHONIOENCODING=utf-8`

## 📈 Progress Tracking

The command shows progress:
- `Importing X patients...`
- `[OK] Imported X patients`
- `Importing X encounters...`
- etc.

## ✅ Verification

After import, verify data:
```python
python manage.py shell
>>> from hospital.models import Patient, Encounter
>>> Patient.objects.count()  # Should show imported patients
>>> Encounter.objects.count()  # Should show imported encounters
```

## 🎯 Next Steps

1. **Review imported data** in Django admin
2. **Check for duplicates** using existing duplicate detection
3. **Verify relationships** (patients → encounters → prescriptions/labs)
4. **Run full import** when ready: `python manage.py import_mysql_legacy`

## 📞 Support

- Command file: `hospital/management/commands/import_mysql_legacy.py`
- MySQL container: `db_2` in `docker-compose.yml`
- SQL files: `import/` directory

---

**Status:** ✅ Ready to use
**Last Updated:** December 17, 2025















