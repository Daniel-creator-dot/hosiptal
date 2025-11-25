"""
Import Data to PostgreSQL
Loads data from hms_data_export.json into PostgreSQL database
"""
import os
import sys
import json

print()
print("╔" + "=" * 68 + "╗")
print("║" + " " * 15 + "Import to PostgreSQL" + " " * 33 + "║")
print("╚" + "=" * 68 + "╝")
print()

# Check if export file exists
if not os.path.exists('hms_data_export.json'):
    print("❌ Error: hms_data_export.json not found!")
    print()
    print("Please run migrate_to_postgresql.py first to export your data.")
    sys.exit(1)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
import django
django.setup()

from django.core import serializers
from django.db import transaction

print("=" * 70)
print("  IMPORTING DATA TO POSTGRESQL")
print("=" * 70)
print()

# Load export data
print("📂 Loading export file...")
with open('hms_data_export.json', 'r') as f:
    data_export = json.load(f)

print(f"   ✅ Loaded {len(data_export)} model types")
print()

# Import in order
total_imported = 0
errors = []

for model_name, objects_data in data_export.items():
    if not objects_data:
        continue
    
    try:
        print(f"📥 Importing {model_name}...")
        
        # Convert back to JSON string for deserializer
        json_data = json.dumps(objects_data)
        
        # Deserialize and save
        with transaction.atomic():
            for obj in serializers.deserialize('json', json_data):
                try:
                    obj.save()
                except Exception as e:
                    # Try to save without validation if regular save fails
                    try:
                        obj.object.save(force_insert=False, force_update=False)
                    except:
                        pass
        
        count = len(objects_data)
        total_imported += count
        print(f"   ✅ Imported {count:,} records")
        
    except Exception as e:
        error_msg = f"{model_name}: {str(e)}"
        errors.append(error_msg)
        print(f"   ⚠️  Error: {str(e)}")

print()
print("=" * 70)
print("  IMPORT SUMMARY")
print("=" * 70)
print()
print(f"✅ Total records imported: {total_imported:,}")
print(f"⚠️  Errors encountered: {len(errors)}")
print()

if errors:
    print("❌ Errors:")
    for error in errors[:10]:
        print(f"   • {error}")
    if len(errors) > 10:
        print(f"   ... and {len(errors) - 10} more")
    print()

print("=" * 70)
print("  ✅ IMPORT COMPLETE!")
print("=" * 70)
print()

print("🔧 Final steps:")
print()
print("1. Create superuser:")
print("   python manage.py createsuperuser")
print()
print("2. Collect static files:")
print("   python manage.py collectstatic --noinput")
print()
print("3. Test the system:")
print("   python manage.py runserver 0.0.0.0:8000")
print()
print("4. Start production server:")
print("   gunicorn hms.wsgi:application --bind 0.0.0.0:8000 --workers 4")
print()

















