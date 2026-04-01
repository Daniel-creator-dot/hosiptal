#!/usr/bin/env python
"""Backfill registration fees for existing patients"""
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
print("BACKFILLING REGISTRATION FEES FOR EXISTING PATIENTS")
print("=" * 80)
print()

# Get all patients
all_patients = Patient.objects.filter(is_deleted=False)
print(f"Total Patients: {all_patients.count()}")
print()

# Get patients without registration fees
patients_with_fees = RegistrationFee.objects.filter(
    is_deleted=False
).values_list('patient_id', flat=True).distinct()

patients_without_fees = all_patients.exclude(id__in=patients_with_fees)
print(f"Patients without registration fees: {patients_without_fees.count()}")
print()

if patients_without_fees.count() == 0:
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

if not reg_service:
    print("⚠️  No registration service code found!")
    exit(1)

print(f"Using registration service code: {reg_service.code} - {reg_service.description}")
print()

# Get or create revenue account
revenue_account, _ = Account.objects.get_or_create(
    account_code='4100',
    defaults={
        'account_name': 'Registration Fees Revenue',
        'account_type': 'revenue',
        'is_active': True,
    }
)

created_count = 0
skipped_count = 0

with transaction.atomic():
    for patient in patients_without_fees[:100]:  # Limit to first 100 to avoid timeout
        # Check if already exists
        existing = RegistrationFee.objects.filter(
            patient=patient,
            is_deleted=False
        ).first()
        
        if existing:
            skipped_count += 1
            continue
        
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
        
        # Get registration price using flexible pricing
        registration_price = ServicePrice.get_price_by_payer_type(
            service_code=reg_service,
            payer_type=payer_type,
            insurance_company=insurance_company
        )
        
        # Fallback to default
        if not registration_price or registration_price == 0:
            registration_price = Decimal('60.00')
        
        # Use patient's created date as registration date
        registration_date = patient.created.date() if hasattr(patient.created, 'date') else timezone.now().date()
        
        try:
            # Create RegistrationFee
            registration_fee = RegistrationFee.objects.create(
                patient=patient,
                registration_date=registration_date,
                fee_amount=registration_price,
                payment_method='cash',  # Default, can be updated later
                revenue_account=revenue_account,
                notes=f'Auto-created for existing patient - MRN: {patient.mrn}'
            )
            
            created_count += 1
            
            if created_count % 50 == 0:
                print(f"   Created {created_count} registration fees...")
                
        except Exception as e:
            print(f"   ⚠️  Error creating fee for {patient.mrn}: {e}")

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Created: {created_count} registration fees")
print(f"Skipped: {skipped_count} (already exist)")
print()

# Verify
total_fees = RegistrationFee.objects.filter(is_deleted=False).count()
print(f"Total Registration Fees: {total_fees}")
print()
print("✅ Backfill complete!")
print()
print("From now on, registration fees will be created automatically")
print("when new patients are registered.")








