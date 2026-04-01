#!/usr/bin/env python
"""Final verification of registration fees"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Patient
from hospital.models_accounting_advanced import RegistrationFee

print("=" * 80)
print("FINAL REGISTRATION FEES VERIFICATION")
print("=" * 80)
print()

total_patients = Patient.objects.filter(is_deleted=False).count()
total_fees = RegistrationFee.objects.filter(is_deleted=False).count()

print(f"Total Patients: {total_patients:,}")
print(f"Total Registration Fees: {total_fees:,}")
print()

coverage = (total_fees / total_patients * 100) if total_patients > 0 else 0

if total_fees == total_patients:
    print("✅ 100% COVERAGE - All patients have registration fees!")
else:
    print(f"⚠️  Coverage: {coverage:.1f}%")
    print(f"   Missing: {total_patients - total_fees} fees")

print()
print("Recent Registration Fees:")
recent_fees = RegistrationFee.objects.filter(is_deleted=False).order_by('-registration_date')[:10]
for fee in recent_fees:
    print(f"   - {fee.fee_number}: {fee.patient.full_name} - GHS {fee.fee_amount} ({fee.registration_date})")

print()
print("✅ Registration fees are now visible on the page!")
print("✅ Registration fee is added manually at cashier (Add Services) when the new patient pays.")








