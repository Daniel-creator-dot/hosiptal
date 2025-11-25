"""
Simple Patient Data Import Script
Imports patient_data table directly
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
    
    print("Importing patient tables...")
    print("  - patient_data (main patient records)")
    print("  - patient_tracker")
    print("  - patient_reminders")
    print()
    
    try:
        # Import patient tables
        call_command(
            'import_legacy_database',
            '--tables',
            'patient_data',
            'patient_tracker',
            'patient_reminders',
            '--skip-drop',
            sql_dir=r'C:\Users\user\Videos\DS'
        )
        
        print()
        print("="*70)
        print("SUCCESS! Patient data imported.")
        print("="*70)
        print()
        
        # Verify
        from django.db import connection
        with connection.cursor() as cursor:
            try:
                cursor.execute('SELECT COUNT(*) FROM patient_data')
                count = cursor.fetchone()[0]
                print(f"Total patient records: {count:,}")
                
                if count > 0:
                    cursor.execute('SELECT id, fname, lname, DOB FROM patient_data LIMIT 5')
                    print()
                    print("Sample patients:")
                    for row in cursor.fetchall():
                        print(f"  ID: {row[0]}, Name: {row[1]} {row[2]}, DOB: {row[3]}")
            except Exception as e:
                print(f"Could not verify: {e}")
        
        print()
        print("Next steps:")
        print("1. View in dbshell: python manage.py dbshell")
        print("2. Validate: python manage.py validate_import")
        print("3. Generate model: python manage.py inspectdb patient_data")
        
    except Exception as e:
        print(f"Error during import: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()




















