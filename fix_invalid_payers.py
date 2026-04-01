"""
Fix patients with invalid payer types
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Patient, Payer

print("="*80)
print("FIXING INVALID PAYERS")
print("="*80)

# Get or create Cash payer
cash_payer, _ = Payer.objects.get_or_create(
    name='Cash',
    defaults={'payer_type': 'cash', 'is_active': True}
)

# Find patients with invalid payers
patients_with_payers = Patient.objects.filter(
    primary_insurance__isnull=False,
    is_deleted=False
).select_related('primary_insurance')

fixed_count = 0
invalid_count = 0

for patient in patients_with_payers:
    payer = patient.primary_insurance
    
    # Check if payer is invalid
    if not payer or not hasattr(payer, 'payer_type') or not payer.payer_type:
        invalid_count += 1
        print(f"\nFixing: {patient.mrn} - {patient.full_name}")
        print(f"  Invalid payer: {payer.name if payer else 'None'}")
        
        # Set to cash payer
        patient.primary_insurance = cash_payer
        patient.save(update_fields=['primary_insurance'])
        fixed_count += 1
        print(f"  Fixed: Set to Cash payer")

print("\n" + "="*80)
print(f"Summary:")
print(f"  Patients checked: {patients_with_payers.count()}")
print(f"  Invalid payers found: {invalid_count}")
print(f"  Fixed: {fixed_count}")
print("="*80)
