"""
Standalone Database Import Script
Imports all SQL files from the DS directory into the hospital database
"""

import os
import sys
import django
import re
from pathlib import Path

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import connection, transaction
from django.core.management import call_command


def main():
    print("="*70)
    print("HOSPITAL DATABASE IMPORT UTILITY")
    print("="*70)
    print("\nThis script will import all legacy SQL files into your database.")
    print("\nOptions:")
    print("1. Import ALL tables (Recommended for first-time setup)")
    print("2. Import SPECIFIC tables only")
    print("3. Import Blood Bank tables only")
    print("4. DRY RUN (see what would be imported)")
    print("5. Exit")
    
    choice = input("\nEnter your choice (1-5): ").strip()
    
    sql_dir = r'C:\Users\user\Videos\DS'
    
    if choice == '1':
        print("\n📦 Starting FULL database import...")
        confirm = input("This will import ALL tables. Continue? (yes/no): ").strip().lower()
        if confirm == 'yes':
            call_command('import_legacy_database', '--sql-dir', sql_dir, '--skip-drop')
        else:
            print("Import cancelled.")
            
    elif choice == '2':
        print("\nAvailable table categories:")
        print("  - Accounting (acc_*)")
        print("  - Admissions (admission_*)")
        print("  - Blood Bank (blood_*)")
        print("  - Forms (form_*)")
        print("  - Insurance (insurance_*)")
        print("  - Laboratory (lab_*)")
        print("  - Patients (patient_*)")
        print("  - Pharmacy (drug_*, prices)")
        print("  - Staff (users*, employee*)")
        
        tables = input("\nEnter table names (space-separated): ").strip().split()
        if tables:
            call_command('import_legacy_database', '--sql-dir', sql_dir, '--tables', *tables, '--skip-drop')
        else:
            print("No tables specified.")
            
    elif choice == '3':
        print("\n🩸 Starting Blood Bank import...")
        blood_tables = ['blood_donors', 'blood_stock']
        call_command('import_legacy_database', '--sql-dir', sql_dir, '--tables', *blood_tables, '--skip-drop')
        
    elif choice == '4':
        print("\n🔍 Running DRY RUN...")
        call_command('import_legacy_database', '--sql-dir', sql_dir, '--dry-run')
        
    elif choice == '5':
        print("Exiting...")
        return
        
    else:
        print("Invalid choice.")
        return
    
    print("\n" + "="*70)
    print("Import process completed!")
    print("="*70)
    
    # Show next steps
    print("\n📋 NEXT STEPS:")
    print("1. Run: python manage.py migrate (to sync Django models)")
    print("2. Check Django admin to verify imported data")
    print("3. Create superuser if needed: python manage.py createsuperuser")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nImport cancelled by user.")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()




















