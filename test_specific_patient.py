"""
Test script for specific patient: Test Patient with phone 0247904675
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Patient

def normalize_phone(phone):
    if not phone:
        return ''
    phone = str(phone).strip()
    phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if phone.startswith('0') and len(phone) == 10:
        phone = '233' + phone[1:]
    elif phone.startswith('+'):
        phone = phone[1:]
    return phone

# Test data
first_name = 'Test'
last_name = 'Patient'
phone = '0247904675'
email = 'test@example.com'
date_of_birth = '1990-01-01'

normalized_phone = normalize_phone(phone)

print("=" * 70)
print("CHECKING FOR EXISTING PATIENT")
print("=" * 70)
print(f"Name: {first_name} {last_name}")
print(f"Phone: {phone} (normalized: {normalized_phone})")
print(f"Email: {email}")
print(f"DOB: {date_of_birth}")
print()

# Check for duplicates
patients = Patient.objects.filter(
    first_name__iexact=first_name,
    last_name__iexact=last_name,
    is_deleted=False
)

print(f"Found {patients.count()} patients with name '{first_name} {last_name}':")
print()

for p in patients:
    p_normalized = normalize_phone(p.phone_number)
    match_phone = p_normalized == normalized_phone
    match_email = p.email and p.email.lower() == email.lower()
    match_dob = str(p.date_of_birth) == date_of_birth
    
    print(f"MRN: {p.mrn}")
    print(f"  Name: {p.full_name}")
    print(f"  Phone: {p.phone_number} (normalized: {p_normalized})")
    print(f"  Email: {p.email}")
    print(f"  DOB: {p.date_of_birth}")
    print(f"  Created: {p.created}")
    print(f"  Match Phone: {'✅' if match_phone else '❌'}")
    print(f"  Match Email: {'✅' if match_email else '❌'}")
    print(f"  Match DOB: {'✅' if match_dob else '❌'}")
    
    if match_phone:
        print(f"  ⚠️  DUPLICATE DETECTED BY PHONE!")
    if match_email:
        print(f"  ⚠️  DUPLICATE DETECTED BY EMAIL!")
    print("-" * 70)

if patients.count() == 0:
    print("✅ No existing patients found - safe to register")
elif patients.count() == 1:
    p = patients.first()
    if normalize_phone(p.phone_number) == normalized_phone:
        print(f"\n⚠️  DUPLICATE EXISTS: {p.mrn}")
        print("   System should block registration of this patient")
    else:
        print(f"\n✅ Different phone number - not a duplicate")
else:
    print(f"\n⚠️  MULTIPLE PATIENTS FOUND - may need cleanup")

print("=" * 70)

