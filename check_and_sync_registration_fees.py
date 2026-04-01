#!/usr/bin/env python
"""Check and sync registration fees in pricing system"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import ServiceCode
from hospital.models_flexible_pricing import PricingCategory, ServicePrice
from hospital.models_pricing import DefaultPrice
from decimal import Decimal
from django.utils import timezone

print("=" * 80)
print("CHECKING AND SYNCING REGISTRATION FEES")
print("=" * 80)
print()

# Check for registration service code
registration_codes = ServiceCode.objects.filter(
    description__icontains='registration',
    is_deleted=False
)

print("1. REGISTRATION SERVICE CODES:")
if registration_codes.exists():
    for code in registration_codes:
        print(f"   ✓ {code.code}: {code.description}")
else:
    print("   ⚠️  No registration service code found")
print()

# Check DefaultPrice for registration
default_registration = DefaultPrice.objects.filter(
    service_code='registration',
    is_deleted=False
).first()

if default_registration:
    print(f"2. DEFAULT REGISTRATION PRICE:")
    print(f"   ✓ {default_registration.description}: GHS {default_registration.default_price}")
else:
    print("2. DEFAULT REGISTRATION PRICE:")
    print("   ⚠️  No default registration price found")
print()

# Get or create registration service code
registration_code, created = ServiceCode.objects.get_or_create(
    code='REG-FEE',
    defaults={
        'description': 'Patient Registration Fee',
        'category': 'Registration',
        'is_active': True,
    }
)

if created:
    print(f"   ✓ Created registration service code: {registration_code.code}")
else:
    print(f"   ✓ Using existing: {registration_code.code} - {registration_code.description}")
print()

# Get all pricing categories
cash_category = PricingCategory.objects.filter(category_type='cash', is_deleted=False).first()
corporate_categories = PricingCategory.objects.filter(category_type='corporate', is_deleted=False)
insurance_categories = PricingCategory.objects.filter(
    category_type='insurance',
    is_deleted=False
).exclude(name__icontains='cash').exclude(name__icontains='other company')

# Get default registration price
default_price = default_registration.default_price if default_registration else Decimal('10.00')

print("3. CHECKING REGISTRATION PRICES IN ALL CATEGORIES:")
print()

created_count = 0
today = timezone.now().date()

# Check cash category
if cash_category:
    cash_price = ServicePrice.objects.filter(
        service_code=registration_code,
        pricing_category=cash_category,
        is_deleted=False
    ).first()
    
    if not cash_price:
        ServicePrice.objects.create(
            service_code=registration_code,
            pricing_category=cash_category,
            price=default_price,
            effective_from=today,
            is_active=True
        )
        created_count += 1
        print(f"   ✓ Created cash price: GHS {default_price}")
    else:
        print(f"   ✓ Cash price exists: GHS {cash_price.price}")

# Check corporate categories
for corp_cat in corporate_categories:
    corp_price = ServicePrice.objects.filter(
        service_code=registration_code,
        pricing_category=corp_cat,
        is_deleted=False
    ).first()
    
    if not corp_price:
        ServicePrice.objects.create(
            service_code=registration_code,
            pricing_category=corp_cat,
            price=default_price,
            effective_from=today,
            is_active=True
        )
        created_count += 1
        print(f"   ✓ Created {corp_cat.name} price: GHS {default_price}")
    else:
        print(f"   ✓ {corp_cat.name} price exists: GHS {corp_price.price}")

# Check insurance categories
for ins_cat in insurance_categories:
    ins_price = ServicePrice.objects.filter(
        service_code=registration_code,
        pricing_category=ins_cat,
        is_deleted=False
    ).first()
    
    if not ins_price:
        ServicePrice.objects.create(
            service_code=registration_code,
            pricing_category=ins_cat,
            price=default_price,
            effective_from=today,
            is_active=True
        )
        created_count += 1
        print(f"   ✓ Created {ins_cat.name} price: GHS {default_price}")
    else:
        print(f"   ✓ {ins_cat.name} price exists: GHS {ins_price.price}")

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Registration Service Code: {registration_code.code} - {registration_code.description}")
print(f"Default Price: GHS {default_price}")
print(f"Created: {created_count} new price entries")
print()

# Verify all categories have registration prices
total_categories = 1 + corporate_categories.count() + insurance_categories.count()
registration_prices = ServicePrice.objects.filter(
    service_code=registration_code,
    is_deleted=False
).count()

print(f"Registration prices in system: {registration_prices} / {total_categories} categories")
print()

if registration_prices == total_categories:
    print("✅ Registration fees are fully synced across all pricing categories!")
else:
    print(f"⚠️  {total_categories - registration_prices} categories still missing registration prices")








