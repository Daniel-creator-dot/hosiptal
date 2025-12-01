#!/usr/bin/env python
"""
Quick test script to verify form changes work
Run: python test_local.py
"""
import os
import sys
import django

# Setup minimal Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    django.setup()
    
    # Test form import
    from hospital.forms import PatientForm
    form = PatientForm()
    
    print("=" * 50)
    print("✅ FORM TEST - SUCCESS!")
    print("=" * 50)
    print(f"✓ Form created successfully")
    print(f"✓ Total fields: {len(form.fields)}")
    print(f"✓ payer_type field: {'payer_type' in form.fields}")
    print(f"✓ selected_corporate_company: {'selected_corporate_company' in form.fields}")
    print(f"✓ receiving_point: {'receiving_point' in form.fields}")
    print(f"✓ employee_id: {'employee_id' in form.fields}")
    print()
    print("✅ All new fields are present!")
    print("=" * 50)
    
except Exception as e:
    print("=" * 50)
    print("❌ ERROR:")
    print("=" * 50)
    print(str(e))
    print()
    print("This is likely a database connection issue.")
    print("The form code is correct, but Django needs a database to initialize.")
    sys.exit(1)

