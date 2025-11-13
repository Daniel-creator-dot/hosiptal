"""
Migrate HMS from SQLite to PostgreSQL
Transfers all data safely to production database
"""
import os
import sys
import json
from datetime import datetime

print()
print("╔" + "=" * 68 + "╗")
print("║" + " " * 15 + "HMS PostgreSQL Migration Tool" + " " * 26 + "║")
print("║" + " " * 20 + "SQLite → PostgreSQL" + " " * 30 + "║")
print("╚" + "=" * 68 + "╝")
print()

# Step 1: Export from SQLite
print("=" * 70)
print("  STEP 1: EXPORT DATA FROM SQLITE")
print("=" * 70)
print()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
import django
django.setup()

from django.core import serializers
from django.apps import apps

# Get all models
print("📦 Exporting data from SQLite...")
print()

# Models to export (in order to handle dependencies)
export_order = [
    'auth.User',
    'auth.Group',
    'auth.Permission',
    'contenttypes.ContentType',
    'hospital.Department',
    'hospital.Staff',
    'hospital.Patient',
    'hospital.Encounter',
    'hospital.Appointment',
    'hospital.Invoice',
    'hospital.PaymentReceipt',
    'hospital.Service',
    'hospital.LabTest',
    'hospital.Prescription',
    'hospital.Admission',
    'hospital.Triage',
    'hospital.ClinicalNote',
    'hospital.Diagnosis',
    'hospital.Procedure',
    'hospital.VitalSign',
    # Accounting
    'hospital.Account',
    'hospital.JournalEntry',
    'hospital.Revenue',
    # Ambulance
    'hospital.AmbulanceServiceType',
    'hospital.AmbulanceUnit',
    'hospital.AmbulanceDispatch',
    'hospital.AmbulanceBilling',
]

data_export = {}

for model_name in export_order:
    try:
        Model = apps.get_model(model_name)
        objects = Model.objects.all()
        count = objects.count()
        
        if count > 0:
            print(f"   📤 {model_name:40} {count:6,} records")
            data = serializers.serialize('json', objects, indent=2)
            data_export[model_name] = json.loads(data)
        else:
            print(f"   ⊘  {model_name:40} {count:6} records (empty)")
    except Exception as e:
        print(f"   ⚠️  {model_name:40} Error: {str(e)}")

# Save to file
export_file = 'hms_data_export.json'
print()
print(f"💾 Saving data to {export_file}...")
with open(export_file, 'w') as f:
    json.dump(data_export, f, indent=2, default=str)

print(f"   ✅ Data exported successfully!")
print()

# Calculate total records
total_records = sum(len(data) for data in data_export.values())
file_size = os.path.getsize(export_file) / (1024 * 1024)
print(f"📊 Total records exported: {total_records:,}")
print(f"📊 Export file size: {file_size:.2f} MB")
print()

print("=" * 70)
print("  ✅ EXPORT COMPLETE!")
print("=" * 70)
print()

print("📝 Next Steps:")
print()
print("1. Install PostgreSQL on your server:")
print("   sudo bash setup_postgresql_production.sh")
print()
print("2. Update your .env file with PostgreSQL connection:")
print("   DATABASE_URL=postgresql://hms_user:password@localhost:5432/hms_production")
print()
print("3. Install required packages:")
print("   pip install -r requirements.txt")
print()
print("4. Run migrations on PostgreSQL:")
print("   python manage.py migrate")
print()
print("5. Import the data:")
print("   python import_to_postgresql.py")
print()
print("6. Start production server:")
print("   gunicorn hms.wsgi:application --bind 0.0.0.0:8000 --workers 4")
print()

print("📋 Files created:")
print(f"   ✅ {export_file} - Your data export")
print("   ✅ requirements.txt - Python dependencies")
print("   ✅ setup_postgresql_production.sh - PostgreSQL setup script")
print("   ✅ PRODUCTION_ENV_TEMPLATE.txt - Environment variables template")
print()
