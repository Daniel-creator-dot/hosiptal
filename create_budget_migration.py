#!/usr/bin/env python
"""
Create migration for Department Budgeting System
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.core.management import call_command

print("=" * 70)
print("Creating Migration for Department Budgeting System")
print("=" * 70)
print()

try:
    # Make migrations
    print("[1/2] Creating migrations...")
    call_command('makemigrations', 'hospital', verbosity=2)
    
    print()
    print("[2/2] Applying migrations...")
    call_command('migrate', 'hospital', verbosity=2)
    
    print()
    print("=" * 70)
    print("[SUCCESS] Migration Complete!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("  1. Run: python setup_department_budgeting.py")
    print("  2. Access: http://127.0.0.1:8000/hms/budget/")
    print()
    
except Exception as e:
    print()
    print("=" * 70)
    print("[ERROR] Migration failed!")
    print("=" * 70)
    print(f"\nError: {str(e)}")
    print()
    print("This is normal if models already exist.")
    print("Try running: python setup_department_budgeting.py directly")
    print()














