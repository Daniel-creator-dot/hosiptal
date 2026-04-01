"""
Fix InsurancePaymentReceived table - add missing processed_by_id column
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import connection

print("="*80)
print("FIXING INSURANCEPAYMENTRECEIVED TABLE")
print("="*80)
print()

with connection.cursor() as cursor:
    # Check if processed_by_id column exists
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'hospital_insurancepaymentreceived'
            AND column_name = 'processed_by_id'
        );
    """)
    column_exists = cursor.fetchone()[0]

if not column_exists:
    print("WARNING: processed_by_id column does not exist!")
    print("   Adding column...")
    
    try:
        with connection.cursor() as cursor:
            # Add the missing column
            cursor.execute("""
                ALTER TABLE hospital_insurancepaymentreceived
                ADD COLUMN IF NOT EXISTS processed_by_id INTEGER REFERENCES auth_user(id);
            """)
        
        print("SUCCESS: processed_by_id column added successfully!")
    except Exception as e:
        print(f"ERROR: Error adding column: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
else:
    print("SUCCESS: processed_by_id column already exists")

print()
print("="*80)
print("SUCCESS: Table fixed!")
print("="*80)


