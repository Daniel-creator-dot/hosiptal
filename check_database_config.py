"""
Script to check database configuration and ensure only one database is being used.
This will help identify if multiple databases are causing duplicate issues.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.conf import settings
from django.db import connection
import sqlite3

print("=" * 70)
print("DATABASE CONFIGURATION CHECK")
print("=" * 70)

# Check Django database configuration
print("\n📊 DJANGO DATABASE CONFIGURATION:")
print(f"   Engine: {settings.DATABASES['default'].get('ENGINE', 'Unknown')}")
print(f"   Name: {settings.DATABASES['default'].get('NAME', 'Unknown')}")
print(f"   Host: {settings.DATABASES['default'].get('HOST', 'Unknown')}")
print(f"   Port: {settings.DATABASES['default'].get('PORT', 'Unknown')}")
print(f"   User: {settings.DATABASES['default'].get('USER', 'Unknown')}")

# Check actual database connection
print("\n🔌 ACTUAL DATABASE CONNECTION:")
try:
    with connection.cursor() as cursor:
        if 'sqlite' in settings.DATABASES['default'].get('ENGINE', ''):
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
            db_path = settings.DATABASES['default'].get('NAME', '')
            print(f"   ✅ Connected to SQLite database: {db_path}")
            print(f"   Database file exists: {os.path.exists(db_path)}")
            if os.path.exists(db_path):
                file_size = os.path.getsize(db_path) / (1024 * 1024)  # MB
                print(f"   Database file size: {file_size:.2f} MB")
        else:
            cursor.execute("SELECT current_database(), version()")
            row = cursor.fetchone()
            print(f"   ✅ Connected to: {row[0]}")
            print(f"   Database version: {row[1]}")
except Exception as e:
    print(f"   ❌ Error connecting to database: {e}")

# Check for multiple SQLite files
print("\n🔍 CHECKING FOR MULTIPLE DATABASE FILES:")
sqlite_files = []
for root, dirs, files in os.walk('.'):
    # Skip virtual environments and common ignore directories
    if any(skip in root for skip in ['venv', 'env', '.git', '__pycache__', 'node_modules']):
        continue
    for file in files:
        if file.endswith('.sqlite3') or file.endswith('.db'):
            full_path = os.path.join(root, file)
            sqlite_files.append(full_path)

if sqlite_files:
    print(f"   ⚠️  Found {len(sqlite_files)} database files:")
    for db_file in sqlite_files:
        size = os.path.getsize(db_file) / (1024 * 1024) if os.path.exists(db_file) else 0
        print(f"      - {db_file} ({size:.2f} MB)")
    print("\n   ⚠️  WARNING: Multiple database files found!")
    print("   This could cause duplicate data if scripts are writing to different databases.")
    print("   Ensure only ONE database is configured in settings.py")
else:
    print("   ✅ No SQLite files found (using PostgreSQL/MySQL)")

# Check patient count
print("\n📈 DATABASE RECORDS:")
try:
    from hospital.models import Patient, Staff
    patient_count = Patient.objects.filter(is_deleted=False).count()
    staff_count = Staff.objects.filter(is_deleted=False).count()
    print(f"   Active Patients: {patient_count}")
    print(f"   Active Staff: {staff_count}")
    
    # Check for obvious duplicates
    from django.db.models import Count
    duplicate_patients = Patient.objects.filter(is_deleted=False).values(
        'first_name', 'last_name', 'date_of_birth'
    ).annotate(count=Count('id')).filter(count__gt=1)
    
    duplicate_count = sum(d['count'] - 1 for d in duplicate_patients)
    if duplicate_count > 0:
        print(f"   ⚠️  Potential duplicate patients: {duplicate_count}")
        print("   Run: python manage.py fix_duplicates --dry-run")
    else:
        print("   ✅ No obvious duplicates found")
        
except Exception as e:
    print(f"   ❌ Error checking records: {e}")

print("\n" + "=" * 70)
print("RECOMMENDATIONS:")
print("=" * 70)
print("1. Ensure only ONE database is configured in .env file (DATABASE_URL)")
print("2. Run: python manage.py fix_duplicates --dry-run (to see duplicates)")
print("3. Run: python manage.py fix_duplicates --fix (to fix duplicates)")
print("4. Check all import scripts to ensure they check for duplicates")
print("=" * 70)

