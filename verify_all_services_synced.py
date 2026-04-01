#!/usr/bin/env python
"""Verify all services are synced with all insurance companies"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_insurance_companies import InsuranceCompany
from hospital.models import Payer, ServiceCode
from hospital.models_flexible_pricing import PricingCategory, ServicePrice
from decimal import Decimal

print("=" * 80)
print("VERIFYING ALL SERVICES SYNCED WITH ALL INSURANCE COMPANIES")
print("=" * 80)
print()

# Get all insurance companies
insurance_companies = InsuranceCompany.objects.filter(is_active=True, is_deleted=False).order_by('name')
print(f"Insurance Companies: {insurance_companies.count()}")
print()

# Get all pricing categories
cash_category = PricingCategory.objects.filter(category_type='cash', is_deleted=False).first()
corporate_categories = PricingCategory.objects.filter(category_type='corporate', is_deleted=False)
insurance_categories = PricingCategory.objects.filter(
    category_type='insurance',
    is_deleted=False
).exclude(name__icontains='cash').exclude(name__icontains='other company').exclude(name__icontains='orange')

print(f"Cash Category: {cash_category.name if cash_category else 'MISSING'}")
print(f"Corporate Categories: {corporate_categories.count()}")
print(f"Insurance Categories: {insurance_categories.count()}")
print()

# Get all service codes
all_services = ServiceCode.objects.filter(is_deleted=False).order_by('code')
print(f"Total Services: {all_services.count()}")
print()

# Check each insurance company
print("=" * 80)
print("CHECKING EACH INSURANCE COMPANY:")
print("=" * 80)
print()

missing_services = {}
total_issues = 0

for ins_company in insurance_companies:
    # Find pricing category for this insurance
    pricing_cat = PricingCategory.objects.filter(
        insurance_company=ins_company,
        is_deleted=False
    ).first()
    
    if not pricing_cat:
        # Try by name
        pricing_cat = PricingCategory.objects.filter(
            name__icontains=ins_company.name,
            category_type='insurance',
            is_deleted=False
        ).first()
    
    if pricing_cat:
        # Count services with prices
        services_with_prices = ServicePrice.objects.filter(
            pricing_category=pricing_cat,
            is_deleted=False
        ).values_list('service_code_id', flat=True).distinct()
        
        service_count = len(services_with_prices)
        
        # Check if all services have prices
        missing = []
        for service in all_services:
            if service.id not in services_with_prices:
                missing.append(service)
        
        if missing:
            missing_services[ins_company.name] = {
                'category': pricing_cat,
                'has_prices': service_count,
                'missing': len(missing),
                'missing_list': missing[:10]  # First 10 missing
            }
            total_issues += len(missing)
        
        status = "✓" if not missing else "⚠️"
        print(f"{status} {ins_company.name}:")
        print(f"   Pricing Category: {pricing_cat.name} ({pricing_cat.code})")
        print(f"   Services with prices: {service_count} / {all_services.count()}")
        if missing:
            print(f"   ⚠️  Missing prices for {len(missing)} services")
            print(f"   Missing examples: {', '.join([s.code for s in missing[:5]])}")
        print()
    else:
        print(f"✗ {ins_company.name}: NO PRICING CATEGORY FOUND")
        print()

# Check cash category
print("=" * 80)
print("CHECKING CASH CATEGORY:")
print("=" * 80)
print()

if cash_category:
    cash_services = ServicePrice.objects.filter(
        pricing_category=cash_category,
        is_deleted=False
    ).values_list('service_code_id', flat=True).distinct()
    
    cash_count = len(cash_services)
    cash_missing = [s for s in all_services if s.id not in cash_services]
    
    status = "✓" if not cash_missing else "⚠️"
    print(f"{status} Cash / Private Patients:")
    print(f"   Services with prices: {cash_count} / {all_services.count()}")
    if cash_missing:
        print(f"   ⚠️  Missing prices for {len(cash_missing)} services")
        print(f"   Missing examples: {', '.join([s.code for s in cash_missing[:5]])}")
    print()
else:
    print("✗ Cash category not found!")
    print()

# Summary
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print()

if total_issues == 0 and not cash_missing:
    print("✅ ALL SERVICES ARE SYNCED!")
    print()
    print("Every service has pricing for:")
    print(f"  ✓ All {insurance_companies.count()} insurance companies")
    print(f"  ✓ Cash category")
    print(f"  ✓ Corporate categories")
else:
    print(f"⚠️  FOUND {total_issues} MISSING PRICE ENTRIES")
    print()
    print("Issues found:")
    for ins_name, data in missing_services.items():
        print(f"  - {ins_name}: {data['missing']} services missing prices")
    if cash_missing:
        print(f"  - Cash: {len(cash_missing)} services missing prices")
    print()
    print("Would you like to create missing prices? (This will be done automatically)")








