"""
Diagnostic script to check legacy patient table status
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import connection

print("=" * 60)
print("LEGACY PATIENT TABLE DIAGNOSTIC")
print("=" * 60)
print()

# Check if patient_data table exists
cursor = connection.cursor()
cursor.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'patient_data'
""")
table_exists = bool(cursor.fetchone())

print(f"1. patient_data table exists: {'✅ YES' if table_exists else '❌ NO'}")
print()

if table_exists:
    # Count records
    try:
        cursor.execute("SELECT COUNT(*) FROM patient_data")
        count = cursor.fetchone()[0]
        print(f"2. Legacy patient records: {count:,}")
        print()
        
        if count > 0:
            # Sample a few records
            cursor.execute("SELECT pid, fname, lname FROM patient_data LIMIT 5")
            samples = cursor.fetchall()
            print("3. Sample records:")
            for pid, fname, lname in samples:
                print(f"   - PID {pid}: {fname} {lname}")
        else:
            print("2. ⚠️  Table exists but is empty!")
    except Exception as e:
        print(f"2. ❌ Error reading table: {e}")
else:
    print("2. ❌ The patient_data table does not exist!")
    print()
    print("SOLUTION:")
    print("   You need to import the legacy patient data.")
    print("   Options:")
    print("   1. If you have a patient_data.sql file:")
    print("      docker-compose exec web python manage.py import_legacy_patients --sql-dir /path/to/sql/files")
    print()
    print("   2. If legacy patients were already migrated to the main Patient table:")
    print("      The legacy table may not be needed. Legacy count will show 0.")
    print("      Check your main Patient table for patients with MRN starting with 'PMC-LEG-'")
    print()

# Check main Patient table for legacy patients
print()
print("=" * 60)
print("MAIN PATIENT TABLE CHECK")
print("=" * 60)
print()

from hospital.models import Patient

# Check for legacy MRNs
legacy_mrns = Patient.objects.filter(mrn__startswith='PMC-LEG-', is_deleted=False).count()
all_patients = Patient.objects.filter(is_deleted=False).count()

print(f"1. Total patients in main table: {all_patients:,}")
print(f"2. Patients with PMC-LEG- MRN: {legacy_mrns:,}")
print()

if legacy_mrns > 0:
    print("✅ Legacy patients appear to have been migrated to the main Patient table!")
    print("   The patient_data table may not be needed anymore.")
    print("   Legacy count showing 0 is expected if all patients were migrated.")
else:
    print("⚠️  No legacy patients found in main Patient table.")
    print("   If you need legacy patient data, you must import it.")

print()
print("=" * 60)





