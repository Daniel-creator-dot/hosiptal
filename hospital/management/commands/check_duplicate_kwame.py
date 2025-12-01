"""
Quick script to check why "kwame jew" duplicates were created
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

# Find all "kwame jew" patients
patients = Patient.objects.filter(
    first_name__iexact='kwame',
    last_name__iexact='jew',
    is_deleted=False
)

print(f"Found {patients.count()} patients named 'kwame jew':")
print("=" * 70)

for p in patients:
    normalized = normalize_phone(p.phone_number)
    print(f"MRN: {p.mrn}")
    print(f"  Name: {p.first_name} {p.last_name}")
    print(f"  DOB: {p.date_of_birth}")
    print(f"  Phone: {p.phone_number} (normalized: {normalized})")
    print(f"  Email: {p.email}")
    print(f"  Created: {p.created}")
    print(f"  Is Deleted: {p.is_deleted}")
    print("-" * 70)

# Check if they're duplicates
if patients.count() > 1:
    print("\n⚠️ DUPLICATES FOUND!")
    print("These patients have:")
    first = patients.first()
    same_dob = all(p.date_of_birth == first.date_of_birth for p in patients)
    same_phone = all(normalize_phone(p.phone_number) == normalize_phone(first.phone_number) for p in patients)
    
    print(f"  Same DOB: {same_dob}")
    print(f"  Same Phone: {same_phone}")
    
    if same_phone:
        print("\n✅ Phone numbers match - should have been caught by duplicate check!")
    else:
        print("\n❌ Phone numbers differ - might be different people")

