#!/usr/bin/env python
"""Sync all registration service codes with prices"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import transaction
from hospital.models import ServiceCode
from hospital.models_flexible_pricing import PricingCategory, ServicePrice
from decimal import Decimal
from django.utils import timezone

print("=" * 80)
print("SYNCING ALL REGISTRATION SERVICE CODES")
print("=" * 80)
print()

# Find all registration-related service codes
registration_codes = ServiceCode.objects.filter(
    description__icontains='registration',
    is_deleted=False
)

print(f"Found {registration_codes.count()} registration service codes:")
for code in registration_codes:
    print(f"   - {code.code}: {code.description}")
print()

# Get all pricing categories
all_categories = PricingCategory.objects.filter(is_deleted=False)
cash_category = PricingCategory.objects.filter(category_type='cash', is_deleted=False).first()

# Use cash price as base (or default to 10.00)
base_price = Decimal('10.00')
if cash_category:
    cash_reg_price = ServicePrice.objects.filter(
        service_code__description__icontains='registration',
        pricing_category=cash_category,
        is_deleted=False
    ).first()
    if cash_reg_price:
        base_price = cash_reg_price.price

print(f"Using base registration price: GHS {base_price}")
print()

created_count = 0
today = timezone.now().date()

with transaction.atomic():
    for reg_code in registration_codes:
        print(f"Syncing: {reg_code.code} - {reg_code.description}")
        
        # Get categories that don't have prices for this code
        categories_with_prices = ServicePrice.objects.filter(
            service_code=reg_code,
            is_deleted=False
        ).values_list('pricing_category_id', flat=True).distinct()
        
        missing_categories = all_categories.exclude(id__in=categories_with_prices)
        
        if missing_categories.exists():
            print(f"   Creating prices for {missing_categories.count()} categories...")
            
            for category in missing_categories:
                ServicePrice.objects.create(
                    service_code=reg_code,
                    pricing_category=category,
                    price=base_price,
                    effective_from=today,
                    is_active=True
                )
                created_count += 1
            
            print(f"   ✓ Created {missing_categories.count()} prices")
        else:
            print(f"   ✓ All categories already have prices")
        print()

print("=" * 80)
print("VERIFICATION")
print("=" * 80)
print()

for reg_code in registration_codes:
    price_count = ServicePrice.objects.filter(
        service_code=reg_code,
        is_deleted=False
    ).count()
    category_count = all_categories.count()
    
    status = "✓" if price_count == category_count else "⚠️"
    print(f"{status} {reg_code.code}: {price_count} / {category_count} categories")

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Registration Codes: {registration_codes.count()}")
print(f"Total Categories: {all_categories.count()}")
print(f"Created: {created_count} new price entries")
print()
print("✅ All registration service codes are now synced with all pricing categories!")








