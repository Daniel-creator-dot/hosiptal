"""
Check if patient tables exist and show data
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import connection


def main():
    print("="*70)
    print("   PATIENT TABLES CHECK")
    print("="*70)
    print()
    
    with connection.cursor() as cursor:
        # Check for patient tables
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            AND name LIKE '%patient%'
            ORDER BY name
        """)
        
        patient_tables = [row[0] for row in cursor.fetchall()]
        
        if not patient_tables:
            print("❌ No patient tables found in database!")
            print()
            print("To import patient data, run:")
            print("   python import_patient_data.py")
            print()
            return
        
        print(f"✅ Found {len(patient_tables)} patient-related tables:")
        print()
        
        # Show details for each table
        for table in patient_tables:
            try:
                cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                count = cursor.fetchone()[0]
                
                print(f"📊 {table}")
                print(f"   Rows: {count:,}")
                
                if count > 0:
                    # Show sample data
                    cursor.execute(f'SELECT * FROM "{table}" LIMIT 1')
                    sample = cursor.fetchone()
                    if sample:
                        print(f"   Sample ID: {sample[0]}")
                
                print()
                
            except Exception as e:
                print(f"   ⚠️  Error: {str(e)}")
                print()
    
    # Check Django Patient model
    print("="*70)
    print("   DJANGO PATIENT MODEL")
    print("="*70)
    print()
    
    try:
        from hospital.models import Patient
        patient_count = Patient.objects.count()
        print(f"✅ Django Patient model exists")
        print(f"   Records: {patient_count:,}")
        
        if patient_count > 0:
            latest = Patient.objects.latest('created')
            print(f"   Latest: {latest.full_name} (MRN: {latest.mrn})")
        else:
            print("   ℹ️  No patients in Django model yet")
            print()
            print("   The legacy patient_data table has different structure.")
            print("   You can:")
            print("   1. Import legacy data: python import_patient_data.py")
            print("   2. Or create new patients in Django admin")
    except Exception as e:
        print(f"⚠️  Django Patient model: {str(e)}")
    
    print()
    print("="*70)


if __name__ == '__main__':
    try:
        main()
        input("\nPress Enter to exit...")
    except KeyboardInterrupt:
        print("\n\nCancelled.")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")




















