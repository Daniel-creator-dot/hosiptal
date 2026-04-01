#!/usr/bin/env python
"""Check for duplicate registration fees and service codes"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting_advanced import RegistrationFee
from hospital.models import ServiceCode, Patient
from hospital.models_flexible_pricing import ServicePrice
from django.db.models import Count

print("=" * 80)
print("CHECKING FOR DUPLICATE REGISTRATION FEES")
print("=" * 80)
print()

# 1. Check duplicate registration fees (same patient, same date)
print("1. DUPLICATE REGISTRATION FEES (Same Patient, Same Date):")
print()

duplicate_fees = RegistrationFee.objects.filter(
    is_deleted=False
).values('patient', 'registration_date').annotate(
    count=Count('id')
).filter(count__gt=1)

if duplicate_fees.exists():
    print(f"   ⚠️  Found {duplicate_fees.count()} duplicate groups:")
    for dup in duplicate_fees:
        patient = Patient.objects.get(id=dup['patient'])
        fees = RegistrationFee.objects.filter(
            patient_id=dup['patient'],
            registration_date=dup['registration_date'],
            is_deleted=False
        )
        print(f"   Patient: {patient.full_name} ({patient.mrn})")
        print(f"   Date: {dup['registration_date']}")
        print(f"   Count: {dup['count']} fees")
        for fee in fees:
            print(f"      - {fee.fee_number}: GHS {fee.fee_amount}")
        print()
else:
    print("   ✓ No duplicate registration fees found")
print()

# 2. Check duplicate fee numbers
print("2. DUPLICATE FEE NUMBERS:")
print()

duplicate_numbers = RegistrationFee.objects.filter(
    is_deleted=False
).values('fee_number').annotate(
    count=Count('id')
).filter(count__gt=1)

if duplicate_numbers.exists():
    print(f"   ⚠️  Found {duplicate_numbers.count()} duplicate fee numbers:")
    for dup in duplicate_numbers:
        fees = RegistrationFee.objects.filter(
            fee_number=dup['fee_number'],
            is_deleted=False
        )
        print(f"   Fee Number: {dup['fee_number']} ({dup['count']} entries)")
        for fee in fees:
            print(f"      - ID: {fee.id}, Patient: {fee.patient.full_name}, Date: {fee.registration_date}")
        print()
else:
    print("   ✓ No duplicate fee numbers found")
print()

# 3. Check duplicate registration service codes
print("3. DUPLICATE REGISTRATION SERVICE CODES:")
print()

registration_codes = ServiceCode.objects.filter(
    description__icontains='registration',
    is_deleted=False
)

# Check for duplicate codes
duplicate_codes = ServiceCode.objects.filter(
    is_deleted=False
).values('code').annotate(
    count=Count('id')
).filter(count__gt=1, code__in=[c.code for c in registration_codes])

if duplicate_codes.exists():
    print(f"   ⚠️  Found {duplicate_codes.count()} duplicate service codes:")
    for dup in duplicate_codes:
        codes = ServiceCode.objects.filter(
            code=dup['code'],
            is_deleted=False
        )
        print(f"   Code: {dup['code']} ({dup['count']} entries)")
        for code in codes:
            print(f"      - ID: {code.id}, Description: {code.description}")
        print()
else:
    print("   ✓ No duplicate registration service codes found")
print()

# 4. Check duplicate service prices for registration
print("4. DUPLICATE SERVICE PRICES FOR REGISTRATION:")
print()

for reg_code in registration_codes:
    duplicate_prices = ServicePrice.objects.filter(
        service_code=reg_code,
        is_deleted=False
    ).values('pricing_category', 'effective_from').annotate(
        count=Count('id')
    ).filter(count__gt=1)
    
    if duplicate_prices.exists():
        print(f"   ⚠️  {reg_code.code} has {duplicate_prices.count()} duplicate price groups:")
        for dup in duplicate_prices:
            prices = ServicePrice.objects.filter(
                service_code=reg_code,
                pricing_category_id=dup['pricing_category'],
                effective_from=dup['effective_from'],
                is_deleted=False
            )
            print(f"      Category: {prices.first().pricing_category.name}")
            print(f"      Effective From: {dup['effective_from']}")
            print(f"      Count: {dup['count']} prices")
            for price in prices:
                print(f"         - ID: {price.id}, Price: GHS {price.price}, Active: {price.is_active}")
            print()
    else:
        print(f"   ✓ {reg_code.code}: No duplicate prices")

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)

total_issues = (
    duplicate_fees.count() +
    duplicate_numbers.count() +
    duplicate_codes.count()
)

if total_issues == 0:
    print("✅ NO DUPLICATES FOUND!")
    print()
    print("All registration fees and service codes are unique.")
else:
    print(f"⚠️  FOUND {total_issues} TYPES OF DUPLICATES")
    print()
    print("Review the details above and fix as needed.")








