"""
Quick test script to verify duplicate prevention is working
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Patient
from django.db.models import Q

def normalize_phone(phone):
    """Normalize phone number for comparison"""
    if not phone:
        return ''
    phone = str(phone).strip()
    phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if phone.startswith('0') and len(phone) == 10:
        phone = '233' + phone[1:]
    elif phone.startswith('+'):
        phone = phone[1:]
    return phone

def test_duplicate_detection():
    """Test if duplicate detection logic works"""
    print("=" * 70)
    print("TESTING DUPLICATE PREVENTION")
    print("=" * 70)
    
    # Get all patients
    all_patients = Patient.objects.filter(is_deleted=False)
    total = all_patients.count()
    print(f"\n📊 Total active patients: {total}")
    
    # Test 1: Check for duplicates by name + DOB + phone
    print("\n🔍 Test 1: Checking for duplicates by Name + DOB + Phone...")
    duplicates_found = 0
    processed = set()
    
    for patient in all_patients:
        if patient.id in processed:
            continue
        
        if not (patient.first_name and patient.last_name and patient.date_of_birth and patient.phone_number):
            continue
        
        normalized_phone = normalize_phone(patient.phone_number)
        
        # Find duplicates
        candidates = Patient.objects.filter(
            first_name__iexact=patient.first_name,
            last_name__iexact=patient.last_name,
            date_of_birth=patient.date_of_birth,
            is_deleted=False
        ).exclude(id=patient.id)
        
        for candidate in candidates:
            if normalize_phone(candidate.phone_number) == normalized_phone:
                duplicates_found += 1
                print(f"   ⚠️  DUPLICATE FOUND:")
                print(f"      Patient 1: {patient.full_name} (MRN: {patient.mrn}, Phone: {patient.phone_number})")
                print(f"      Patient 2: {candidate.full_name} (MRN: {candidate.mrn}, Phone: {candidate.phone_number})")
                processed.add(patient.id)
                processed.add(candidate.id)
                break
    
    # Test 2: Check for duplicates by email
    print("\n🔍 Test 2: Checking for duplicates by Email...")
    email_duplicates = 0
    processed_emails = set()
    
    for patient in all_patients:
        if patient.id in processed_emails or not patient.email:
            continue
        
        existing = Patient.objects.filter(
            email__iexact=patient.email,
            is_deleted=False
        ).exclude(id=patient.id).first()
        
        if existing:
            email_duplicates += 1
            print(f"   ⚠️  DUPLICATE FOUND:")
            print(f"      Patient 1: {patient.full_name} (MRN: {patient.mrn}, Email: {patient.email})")
            print(f"      Patient 2: {existing.full_name} (MRN: {existing.mrn}, Email: {existing.email})")
            processed_emails.add(patient.id)
            processed_emails.add(existing.id)
    
    # Test 3: Check for duplicates by national_id
    print("\n🔍 Test 3: Checking for duplicates by National ID...")
    national_id_duplicates = 0
    processed_national_ids = set()
    
    for patient in all_patients:
        if patient.id in processed_national_ids or not patient.national_id:
            continue
        
        existing = Patient.objects.filter(
            national_id=patient.national_id,
            is_deleted=False
        ).exclude(id=patient.id).first()
        
        if existing:
            national_id_duplicates += 1
            print(f"   ⚠️  DUPLICATE FOUND:")
            print(f"      Patient 1: {patient.full_name} (MRN: {patient.mrn}, National ID: {patient.national_id})")
            print(f"      Patient 2: {existing.full_name} (MRN: {existing.mrn}, National ID: {existing.national_id})")
            processed_national_ids.add(patient.id)
            processed_national_ids.add(existing.id)
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST RESULTS")
    print("=" * 70)
    print(f"Total patients checked: {total}")
    print(f"Duplicates by Name+DOB+Phone: {duplicates_found}")
    print(f"Duplicates by Email: {email_duplicates}")
    print(f"Duplicates by National ID: {national_id_duplicates}")
    print(f"Total duplicate sets found: {duplicates_found + email_duplicates + national_id_duplicates}")
    
    if duplicates_found == 0 and email_duplicates == 0 and national_id_duplicates == 0:
        print("\n✅ NO DUPLICATES FOUND! System is working correctly.")
        print("\n💡 To test prevention:")
        print("   1. Go to: http://localhost:8000/hms/patients/new/")
        print("      OR: http://localhost:8000/hms/patient-registration/")
        print("   2. Register a patient")
        print("   3. Try to register the same patient again")
        print("   4. You should see a duplicate error message")
    else:
        print("\n⚠️  DUPLICATES FOUND! Run this to fix them:")
        print("   python manage.py fix_duplicates --fix")
    
    print("=" * 70)

if __name__ == '__main__':
    test_duplicate_detection()

