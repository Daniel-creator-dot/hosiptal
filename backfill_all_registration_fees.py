#!/usr/bin/env python
"""Backfill ALL registration fees for existing patients in batches"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from hospital.models import Patient, ServiceCode, Payer
from hospital.models_flexible_pricing import ServicePrice
from hospital.models_accounting_advanced import RegistrationFee, Account
from hospital.models_insurance_companies import InsuranceCompany

print("=" * 80)
print("BACKFILLING ALL REGISTRATION FEES")
print("=" * 80)
print()

# Get all patients without registration fees
all_patients = Patient.objects.filter(is_deleted=False)
patients_with_fees = RegistrationFee.objects.filter(
    is_deleted=False
).values_list('patient_id', flat=True).distinct()

patients_without_fees = all_patients.exclude(id__in=patients_with_fees)
total_to_process = patients_without_fees.count()

print(f"Total Patients: {all_patients.count()}")
print(f"Patients with fees: {len(patients_with_fees)}")
print(f"Patients without fees: {total_to_process}")
print()

if total_to_process == 0:
    print("✅ All patients already have registration fees!")
    exit(0)

# Get registration service code
reg_service = ServiceCode.objects.filter(
    code='REG',
    is_deleted=False
).first()

if not reg_service:
    reg_service = ServiceCode.objects.filter(
        code='REG-FEE',
        is_deleted=False
    ).first()

# Get or create revenue account
revenue_account, _ = Account.objects.get_or_create(
    account_code='4100',
    defaults={
        'account_name': 'Registration Fees Revenue',
        'account_type': 'revenue',
        'is_active': True,
    }
)

BATCH_SIZE = 500
total_created = 0
batch_num = 0

while True:
    batch = patients_without_fees[total_created:total_created + BATCH_SIZE]
    if not batch.exists():
        break
    
    batch_num += 1
    print(f"Processing batch {batch_num} ({len(batch)} patients)...")
    
    with transaction.atomic():
        for patient in batch:
            # Get patient's payer
            payer = patient.primary_insurance
            payer_type = 'cash'
            insurance_company = None
            
            if payer:
                payer_type = payer.payer_type or 'cash'
                if payer_type == 'insurance':
                    insurance_company = InsuranceCompany.objects.filter(
                        name__iexact=payer.name,
                        is_active=True,
                        is_deleted=False
                    ).first()
            
            # Get registration price
            registration_price = None
            if reg_service:
                registration_price = ServicePrice.get_price_by_payer_type(
                    service_code=reg_service,
                    payer_type=payer_type,
                    insurance_company=insurance_company
                )
            
            if not registration_price or registration_price == 0:
                registration_price = Decimal('60.00')
            
            # Use patient's created date
            registration_date = patient.created.date() if hasattr(patient.created, 'date') else timezone.now().date()
            
            try:
                RegistrationFee.objects.create(
                    patient=patient,
                    registration_date=registration_date,
                    fee_amount=registration_price,
                    payment_method='cash',
                    revenue_account=revenue_account,
                    notes=f'Auto-created for existing patient - MRN: {patient.mrn}'
                )
                total_created += 1
            except Exception as e:
                print(f"   ⚠️  Error for {patient.mrn}: {e}")
    
    print(f"   ✓ Batch {batch_num} complete: {total_created} total created")
    print()

print("=" * 80)
print("FINAL SUMMARY")
print("=" * 80)
print(f"Created: {total_created} registration fees")
print(f"Total Registration Fees: {RegistrationFee.objects.filter(is_deleted=False).count()}")
print()
print("✅ All registration fees backfilled!")








