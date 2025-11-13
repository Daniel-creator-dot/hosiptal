#!/usr/bin/env python
"""
Database Update Script
Creates and applies migrations for new models
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.core.management import execute_from_command_line

def main():
    print("=" * 60)
    print("Hospital Management System - Database Update")
    print("=" * 60)
    
    try:
        # Step 1: Create migrations
        print("\n[1/3] Creating migrations...")
        execute_from_command_line(['manage.py', 'makemigrations', 'hospital', '--name', 'add_missing_features'])
        print("✓ Migrations created successfully")
        
        # Step 2: Apply migrations
        print("\n[2/3] Applying migrations...")
        execute_from_command_line(['manage.py', 'migrate'])
        print("✓ Migrations applied successfully")
        
        # Step 3: Show migration status
        print("\n[3/3] Migration status:")
        execute_from_command_line(['manage.py', 'showmigrations', 'hospital'])
        
        print("\n" + "=" * 60)
        print("Database update completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error during database update: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Ensure all dependencies are installed: pip install -r requirements.txt")
        print("2. Check database connection settings in hms/settings.py")
        print("3. Verify models_missing_features.py has no syntax errors")
        sys.exit(1)

if __name__ == '__main__':
    main()

