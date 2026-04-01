"""
Check and fix patients with invalid payer data
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Patient, Payer

print("="*80)
print("CHECKING FOR INVALID PAYERS")
print("="*80)

# Get or create Cash payer
cash_payer, _ = Payer.objects.get_or_create(
    name='Cash',
    defaults={'payer_type': 'cash', 'is_active': True}
)

# Find all patients with payers
patients = Patient.objects.filter(
    primary_insurance__isnull=False,
    is_deleted=False
).select_related('primary_insurance')

print(f"\nChecking {patients.count()} patients with payers...\n")

fixed_count = 0
invalid_payers = []

for patient in patients:
    payer = patient.primary_insurance
    
    if not payer:
        continue
    
    # Check for invalid payer_type
    payer_type = getattr(payer, 'payer_type', None)
    payer_name = getattr(payer, 'name', 'Unknown')
    
    # Check if payer_type is empty, None, or not in valid choices
    valid_types = ['cash', 'insurance', 'private', 'nhis', 'corporate']
    
    if not payer_type or payer_type.strip() == '' or payer_type not in valid_types:
        invalid_payers.append({
            'patient': patient,
            'payer': payer,
            'payer_type': payer_type,
            'payer_name': payer_name
        })
        print(f"INVALID: {patient.mrn} - {patient.full_name}")
        print(f"  Payer: {payer_name}")
        print(f"  Payer Type: '{payer_type}' (invalid)")
        
        # Fix it
        patient.primary_insurance = cash_payer
        patient.save(update_fields=['primary_insurance'])
        fixed_count += 1
        print(f"  FIXED: Set to Cash payer\n")

print("\n" + "="*80)
print(f"Summary:")
print(f"  Patients checked: {patients.count()}")
print(f"  Invalid payers found: {len(invalid_payers)}")
print(f"  Fixed: {fixed_count}")
print("="*80)

if invalid_payers:
    print("\nInvalid Payers Fixed:")
    for item in invalid_payers:
        print(f"  - {item['patient'].mrn}: {item['payer_name']} (type: '{item['payer_type']}')")
