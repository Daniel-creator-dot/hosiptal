"""
Verify Legacy Patients Setup
Check if legacy patient data is accessible via Django
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()


def main():
    print("="*70)
    print("LEGACY PATIENT DATA VERIFICATION")
    print("="*70)
    print()
    
    # Check if table exists
    print("1. Checking if patient_data table exists...")
    from django.db import connection
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='patient_data'
        """)
        result = cursor.fetchone()
        
        if result:
            print("   [OK] patient_data table exists")
        else:
            print("   [ERROR] patient_data table NOT found")
            print("   Run: python import_patient_final.py")
            return
    
    # Check record count
    print("\n2. Checking record count...")
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) FROM patient_data')
        count = cursor.fetchone()[0]
        print(f"   [OK] Found {count:,} patient records")
    
    # Try to import model
    print("\n3. Checking Django model...")
    try:
        from hospital.models_legacy_patients import LegacyPatient
        print("   [OK] LegacyPatient model imported")
        
        # Query using Django ORM
        total = LegacyPatient.objects.count()
        print(f"   [OK] Django ORM count: {total:,} patients")
        
    except Exception as e:
        print(f"   [ERROR] Model import failed: {e}")
        return
    
    # Check admin
    print("\n4. Checking admin registration...")
    try:
        from hospital.admin_legacy_patients import LegacyPatientAdmin
        from django.contrib import admin
        
        if LegacyPatient in admin.site._registry:
            print("   [OK] LegacyPatient registered in admin")
        else:
            print("   [WARNING] LegacyPatient not registered")
            
    except Exception as e:
        print(f"   [WARNING] Admin check: {e}")
    
    # Show sample data
    print("\n5. Sample legacy patients:")
    print("-"*70)
    
    patients = LegacyPatient.objects.filter(fname__isnull=False).exclude(fname='')[:10]
    
    for p in patients:
        print(f"   {p.pid:6d} | {p.full_name:30s} | {p.sex:6s} | {p.display_phone}")
    
    print()
    print("="*70)
    print("VERIFICATION COMPLETE!")
    print("="*70)
    print()
    print("✅ Legacy patient data is accessible via Django!")
    print()
    print("To view in admin:")
    print("1. Run: python manage.py runserver")
    print("2. Visit: http://127.0.0.1:8000/admin/")
    print("3. Look for: LEGACY PATIENTS")
    print()
    print("You should see 35,019 legacy patient records!")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()




















