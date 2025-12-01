"""
Check Patient Database - Verify all patient data sources
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import connection
from hospital.models import Patient
from django.db.models import Q

def check_database_tables():
    """Check what patient-related tables exist"""
    print("="*70)
    print("   PATIENT DATABASE TABLES CHECK")
    print("="*70)
    print()
    
    with connection.cursor() as cursor:
        # Get database vendor
        vendor = connection.vendor
        print(f"Database: {vendor}")
        print()
        
        if vendor == 'postgresql':
            # PostgreSQL
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name LIKE '%patient%'
                ORDER BY table_name
            """)
        else:
            # SQLite
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' 
                AND name LIKE '%patient%'
                ORDER BY name
            """)
        
        tables = [row[0] for row in cursor.fetchall()]
        
        if not tables:
            print("❌ No patient tables found!")
            return []
        
        print(f"✅ Found {len(tables)} patient-related tables:")
        print()
        
        table_info = []
        for table in tables:
            try:
                if vendor == 'postgresql':
                    cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                else:
                    cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                count = cursor.fetchone()[0]
                
                print(f"📊 {table}: {count:,} rows")
                table_info.append((table, count))
                
            except Exception as e:
                print(f"   ⚠️  Error checking {table}: {str(e)}")
        
        return table_info


def check_django_patients():
    """Check Django Patient model"""
    print()
    print("="*70)
    print("   DJANGO PATIENT MODEL (hospital.models.Patient)")
    print("="*70)
    print()
    
    try:
        # Total count
        total = Patient.objects.filter(is_deleted=False).count()
        print(f"✅ Total Patients (not deleted): {total:,}")
        
        # With phone numbers
        with_phone = Patient.objects.filter(
            is_deleted=False
        ).exclude(
            Q(phone_number__isnull=True) | Q(phone_number='')
        ).count()
        print(f"   📱 With phone numbers: {with_phone:,}")
        
        # Recent patients
        recent = Patient.objects.filter(is_deleted=False).order_by('-created')[:5]
        if recent:
            print()
            print("   Recent Patients:")
            for p in recent:
                print(f"      - {p.full_name} ({p.mrn}) - Created: {p.created.date()}")
        else:
            print()
            print("   ⚠️  No patients found in database")
        
        return total
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 0


def check_legacy_patients():
    """Check LegacyPatient model"""
    print()
    print("="*70)
    print("   LEGACY PATIENT MODEL (hospital.models_legacy_patients.LegacyPatient)")
    print("="*70)
    print()
    
    try:
        from hospital.models_legacy_patients import LegacyPatient
        
        total = LegacyPatient.objects.count()
        print(f"✅ Total Legacy Patients: {total:,}")
        
        if total > 0:
            # Sample patients
            sample = LegacyPatient.objects.all()[:5]
            print()
            print("   Sample Legacy Patients:")
            for p in sample:
                print(f"      - {p.full_name} (PID: {p.pid}, MRN: {p.mrn_display})")
        else:
            print()
            print("   ⚠️  No legacy patients found")
        
        return total
        
    except ImportError:
        print("   ⚠️  LegacyPatient model not found")
        return 0
    except Exception as e:
        print(f"   ⚠️  Error: {str(e)}")
        # Check if table exists directly
        try:
            with connection.cursor() as cursor:
                vendor = connection.vendor
                if vendor == 'postgresql':
                    cursor.execute("SELECT COUNT(*) FROM hospital_legacypatient")
                else:
                    cursor.execute("SELECT COUNT(*) FROM hospital_legacypatient")
                count = cursor.fetchone()[0]
                print(f"   📊 Direct table check: {count:,} rows in hospital_legacypatient")
                return count
        except:
            return 0


def check_patient_data_table():
    """Check patient_data table (legacy SQL table)"""
    print()
    print("="*70)
    print("   LEGACY PATIENT_DATA TABLE (Direct SQL)")
    print("="*70)
    print()
    
    try:
        with connection.cursor() as cursor:
            vendor = connection.vendor
            if vendor == 'postgresql':
                # Check if table exists
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'patient_data'
                    )
                """)
                exists = cursor.fetchone()[0]
                
                if exists:
                    cursor.execute("SELECT COUNT(*) FROM patient_data")
                    count = cursor.fetchone()[0]
                    print(f"✅ patient_data table exists: {count:,} rows")
                    
                    if count > 0:
                        cursor.execute("SELECT fname, lname, DOB, sex FROM patient_data LIMIT 5")
                        samples = cursor.fetchall()
                        print()
                        print("   Sample Records:")
                        for s in samples:
                            print(f"      - {s[0]} {s[1]} (DOB: {s[2]}, Sex: {s[3]})")
                else:
                    print("   ⚠️  patient_data table does not exist")
                    return 0
            else:
                # SQLite
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='patient_data'
                """)
                if cursor.fetchone():
                    cursor.execute("SELECT COUNT(*) FROM patient_data")
                    count = cursor.fetchone()[0]
                    print(f"✅ patient_data table exists: {count:,} rows")
                    
                    if count > 0:
                        cursor.execute("SELECT fname, lname, DOB, sex FROM patient_data LIMIT 5")
                        samples = cursor.fetchall()
                        print()
                        print("   Sample Records:")
                        for s in samples:
                            print(f"      - {s[0]} {s[1]} (DOB: {s[2]}, Sex: {s[3]})")
                else:
                    print("   ⚠️  patient_data table does not exist")
                    return 0
            
            return count if 'count' in locals() else 0
            
    except Exception as e:
        print(f"   ⚠️  Error checking patient_data: {str(e)}")
        return 0


def main():
    """Main function"""
    print()
    print("🔍 PATIENT DATABASE VERIFICATION")
    print()
    
    # Check tables
    tables = check_database_tables()
    
    # Check Django Patient model
    django_count = check_django_patients()
    
    # Check LegacyPatient model
    legacy_count = check_legacy_patients()
    
    # Check patient_data table
    patient_data_count = check_patient_data_table()
    
    # Summary
    print()
    print("="*70)
    print("   SUMMARY")
    print("="*70)
    print()
    print(f"📊 Django Patient Model:     {django_count:,} patients")
    print(f"📊 LegacyPatient Model:      {legacy_count:,} patients")
    print(f"📊 patient_data Table:      {patient_data_count:,} patients")
    print()
    print(f"📊 TOTAL:                    {django_count + legacy_count + patient_data_count:,} patient records")
    print()
    
    if django_count == 0 and legacy_count == 0 and patient_data_count == 0:
        print("⚠️  WARNING: No patients found in any database!")
        print()
        print("To add patients:")
        print("  1. Go to: http://127.0.0.1:8000/hms/patients/new/")
        print("  2. Or use Django admin: http://127.0.0.1:8000/admin/hospital/patient/")
        print()
    elif django_count == 0:
        print("💡 TIP: No new patients found. Legacy patients are available.")
        print("   Use the 'Source' filter on the patient list page to view legacy patients.")
        print()
    else:
        print("✅ Patient database is populated!")
        print()


if __name__ == '__main__':
    main()


