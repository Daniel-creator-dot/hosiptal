"""
Import Patient Data from Legacy Database
Quick script to import patient-related tables
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.core.management import call_command


def main():
    print("="*70)
    print("   PATIENT DATA IMPORT")
    print("="*70)
    print()
    
    print("📊 Patient-related tables found:")
    patient_tables = [
        'patient_data',              # Main patient records
        'patient_reminders',         # Patient reminders
        'patient_tracker',           # Patient tracking
        'patient_tracker_element',   # Tracking elements
        'patient_access_onsite',     # Onsite access
        'patient_access_offsite',    # Offsite access
        'patient_portal_menu',       # Portal menu
    ]
    
    for table in patient_tables:
        print(f"   - {table}")
    
    print()
    print("This will import patient demographic and tracking data.")
    print()
    
    confirm = input("Import patient tables? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("Import cancelled.")
        return
    
    print()
    print("🚀 Starting import...")
    print()
    
    # Get the correct SQL directory path
    sql_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'import', 'legacy')
    
    print(f"📁 SQL Directory: {sql_dir}")
    print()
    
    # First, import the raw SQL tables
    print("Step 1: Importing raw SQL tables...")
    call_command(
        'import_legacy_database',
        '--tables',
        *patient_tables,
        '--skip-drop',
        sql_dir=sql_dir
    )
    
    print()
    print("Step 2: Creating Patient model records from imported data...")
    # Then, create Patient model records from the imported data
    call_command(
        'import_legacy_patients',
        '--sql-dir',
        sql_dir,
        '--patients-only'
    )
    
    print()
    print("="*70)
    print("✅ Patient data import complete!")
    print("="*70)
    print()
    print("Next steps:")
    print("1. Verify: python manage.py dbshell")
    print("   Then: SELECT COUNT(*) FROM patient_data;")
    print()
    print("2. Validate: python manage.py validate_import")
    print()
    print("3. View in admin: python manage.py runserver")
    print("   Visit: http://127.0.0.1:8000/admin/")
    print()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nImport cancelled by user.")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()




















