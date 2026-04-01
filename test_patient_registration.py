#!/usr/bin/env python
"""
Test patient registration to diagnose issues
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Patient, Department
from hospital.forms import PatientForm
from django.utils import timezone
from datetime import date

print("\n" + "="*80)
print("PATIENT REGISTRATION DIAGNOSTIC TEST")
print("="*80 + "\n")

# Test 1: Check if Patient model is accessible
print("1. Testing Patient model...")
try:
    patient_count = Patient.objects.filter(is_deleted=False).count()
    print(f"   ✅ Patient model accessible - {patient_count} patients in database")
except Exception as e:
    print(f"   ❌ ERROR accessing Patient model: {e}")
    sys.exit(1)

# Test 2: Check if Department exists (needed for encounter creation)
print("\n2. Testing Department model...")
try:
    dept_count = Department.objects.filter(is_deleted=False).count()
    print(f"   ✅ Department model accessible - {dept_count} departments")
    if dept_count == 0:
        print("   ⚠️  WARNING: No departments found! Patient registration may fail when creating encounter.")
except Exception as e:
    print(f"   ❌ ERROR accessing Department model: {e}")

# Test 3: Test PatientForm with sample data
print("\n3. Testing PatientForm validation...")
try:
    test_data = {
        'first_name': 'Test',
        'last_name': 'Patient',
        'date_of_birth': '1990-01-01',
        'gender': 'M',
        'phone_number': '0241234567',
        'address': 'Test Address',
        'payer_type': 'cash',
    }
    
    form = PatientForm(data=test_data)
    is_valid = form.is_valid()
    
    if is_valid:
        print("   ✅ PatientForm validation passed")
        print(f"   ✅ Cleaned data: {list(form.cleaned_data.keys())}")
    else:
        print("   ❌ PatientForm validation FAILED")
        print(f"   ❌ Errors: {form.errors}")
        print(f"   ❌ Non-field errors: {form.non_field_errors()}")
except Exception as e:
    print(f"   ❌ ERROR testing PatientForm: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Test MRN generation
print("\n4. Testing MRN generation...")
try:
    mrn = Patient.generate_mrn()
    print(f"   ✅ MRN generated: {mrn}")
    
    # Check if MRN already exists
    if Patient.objects.filter(mrn=mrn, is_deleted=False).exists():
        print(f"   ⚠️  WARNING: Generated MRN {mrn} already exists!")
    else:
        print(f"   ✅ Generated MRN is unique")
except Exception as e:
    print(f"   ❌ ERROR generating MRN: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Test creating a patient (dry run - don't save)
print("\n5. Testing patient creation (dry run)...")
try:
    test_data = {
        'first_name': 'Diagnostic',
        'last_name': 'Test',
        'date_of_birth': date(1990, 1, 1),
        'gender': 'M',
        'phone_number': '0249999999',
        'address': 'Test Address',
    }
    
    # Create patient instance but don't save
    patient = Patient(**test_data)
    
    # Check if MRN would be generated
    if not patient.mrn:
        patient.mrn = Patient.generate_mrn()
    
    print(f"   ✅ Patient instance created successfully")
    print(f"   ✅ MRN would be: {patient.mrn}")
    print(f"   ✅ Full name: {patient.full_name}")
    
    # Check for duplicates
    normalized_phone = patient.phone_number.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if normalized_phone.startswith('0') and len(normalized_phone) == 10:
        normalized_phone = '233' + normalized_phone[1:]
    
    existing = Patient.objects.filter(
        first_name__iexact=patient.first_name,
        last_name__iexact=patient.last_name,
        is_deleted=False
    ).first()
    
    if existing:
        existing_normalized = existing.phone_number.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        if existing_normalized.startswith('0') and len(existing_normalized) == 10:
            existing_normalized = '233' + existing_normalized[1:]
        
        if existing_normalized == normalized_phone:
            print(f"   ⚠️  WARNING: Duplicate patient would be detected: {existing.mrn}")
        else:
            print(f"   ✅ No duplicate detected (different phone)")
    else:
        print(f"   ✅ No duplicate detected")
        
except Exception as e:
    print(f"   ❌ ERROR testing patient creation: {e}")
    import traceback
    traceback.print_exc()

# Test 6: Check database connection
print("\n6. Testing database connection...")
try:
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        if result:
            print("   ✅ Database connection working")
        else:
            print("   ❌ Database connection issue")
except Exception as e:
    print(f"   ❌ ERROR with database connection: {e}")

# Test 7: Check for missing required fields
print("\n7. Checking Patient model required fields...")
try:
    from django.db import models
    patient_fields = Patient._meta.get_fields()
    required_fields = []
    for field in patient_fields:
        if hasattr(field, 'blank') and not field.blank and hasattr(field, 'null') and not field.null:
            if field.name != 'id' and field.name != 'mrn':  # Skip auto-generated fields
                required_fields.append(field.name)
    
    print(f"   ✅ Required fields (excluding auto-generated): {required_fields}")
except Exception as e:
    print(f"   ⚠️  Could not check required fields: {e}")

print("\n" + "="*80)
print("DIAGNOSTIC TEST COMPLETE")
print("="*80 + "\n")








