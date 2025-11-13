"""
Update Legacy Patient IDs to Use PMC Prefix
Makes all patients use consistent PMC format
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
    print("UPDATE LEGACY PATIENTS TO USE PMC PREFIX")
    print("="*70)
    print()
    
    print("This will update all legacy patient IDs to use PMC prefix.")
    print()
    print("Examples:")
    print("  PID 1     -> PMC-LEG-000001")
    print("  PID 2     -> PMC-LEG-000002")
    print("  PID 2021  -> PMC-LEG-002021")
    print("  PID 35023 -> PMC-LEG-035023")
    print()
    
    confirm = input("Continue? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("Cancelled.")
        return
    
    print()
    print("Adding PMC_MRN column to patient_data table...")
    
    with connection.cursor() as cursor:
        # Add new column for PMC MRN
        try:
            cursor.execute('ALTER TABLE patient_data ADD COLUMN pmc_mrn TEXT')
            print("[OK] Added pmc_mrn column")
        except Exception as e:
            if 'duplicate column' in str(e).lower():
                print("[INFO] Column already exists")
            else:
                print(f"[ERROR] {e}")
                return
        
        # Update all records with PMC format
        print()
        print("Updating patient records with PMC prefix...")
        
        cursor.execute('SELECT COUNT(*) FROM patient_data')
        total = cursor.fetchone()[0]
        
        print(f"Processing {total:,} patient records...")
        print()
        
        # Update in batches for performance
        cursor.execute('''
            UPDATE patient_data 
            SET pmc_mrn = 'PMC-LEG-' || printf('%06d', pid)
            WHERE pid IS NOT NULL AND pid > 0
        ''')
        
        connection.connection.commit()
        
        print("[OK] All patients updated with PMC prefix!")
        
        # Verify
        print()
        print("Verification:")
        cursor.execute('''
            SELECT id, fname, lname, pid, pmc_mrn 
            FROM patient_data 
            WHERE pmc_mrn IS NOT NULL 
            LIMIT 10
        ''')
        
        print()
        print("Sample updated records:")
        print("-"*70)
        for row in cursor.fetchall():
            print(f"  {row[1]} {row[2]:20s} | PID: {row[3]:6d} -> MRN: {row[4]}")
        
        # Count updated
        cursor.execute('SELECT COUNT(*) FROM patient_data WHERE pmc_mrn IS NOT NULL')
        updated = cursor.fetchone()[0]
        
        print()
        print("="*70)
        print(f"SUCCESS! Updated {updated:,} patient records")
        print("="*70)
        print()
        print("All legacy patients now have PMC prefix!")
        print()
        print("Next steps:")
        print("1. Restart server: python manage.py runserver")
        print("2. Refresh page: http://127.0.0.1:8000/hms/patients/")
        print("3. All patients will now show PMC-LEG-XXXXXX format")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

