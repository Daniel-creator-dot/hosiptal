#!/usr/bin/env python
"""
Simple wrapper script to run the legacy data migration
Run this instead of managing.py directly for easier access
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.core.management import call_command

if __name__ == '__main__':
    print("="*70)
    print("LEGACY DATA MIGRATION RUNNER")
    print("="*70)
    print()
    
    # Default SQL directory
    sql_dir = os.path.join(os.path.dirname(__file__), 'import', 'db_3_extracted')
    
    if not os.path.exists(sql_dir):
        print(f"❌ ERROR: SQL directory not found: {sql_dir}")
        print("\nPlease ensure the SQL files are in the correct location:")
        print("  - import/db_3_extracted/patient_data.sql")
        print("  - import/db_3_extracted/drugs.sql")
        print("  - import/db_3_extracted/codes.sql")
        print("  - etc.")
        sys.exit(1)
    
    print(f"✓ SQL directory found: {sql_dir}")
    print()
    
    # Ask user what they want to do
    print("Migration Options:")
    print("  1. Dry Run (Preview - no changes)")
    print("  2. Full Migration (Import everything)")
    print("  3. Skip Duplicates (Don't update existing)")
    print("  4. Exit")
    print()
    
    choice = input("Select option (1-4): ").strip()
    
    if choice == '1':
        print("\n🔍 Running DRY RUN...\n")
        call_command('migrate_legacy_data', 
                    sql_dir=sql_dir, 
                    dry_run=True)
    elif choice == '2':
        print("\n⚠️  WARNING: This will import and update data in your database!")
        confirm = input("Type 'yes' to continue: ").strip().lower()
        if confirm == 'yes':
            print("\n🚀 Starting full migration...\n")
            call_command('migrate_legacy_data', 
                        sql_dir=sql_dir,
                        update_existing=True)
        else:
            print("Migration cancelled.")
    elif choice == '3':
        print("\n⚠️  WARNING: This will import data but skip existing records!")
        confirm = input("Type 'yes' to continue: ").strip().lower()
        if confirm == 'yes':
            print("\n🚀 Starting migration (skip duplicates)...\n")
            call_command('migrate_legacy_data', 
                        sql_dir=sql_dir,
                        skip_duplicates=True)
        else:
            print("Migration cancelled.")
    elif choice == '4':
        print("Exiting...")
        sys.exit(0)
    else:
        print("Invalid choice.")
        sys.exit(1)
    
    print("\n" + "="*70)
    print("Migration completed!")
    print("="*70)
