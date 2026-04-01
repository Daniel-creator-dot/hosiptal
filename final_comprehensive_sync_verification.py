#!/usr/bin/env python
"""Final comprehensive verification of all pricing sync"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_insurance_companies import InsuranceCompany
from hospital.models import ServiceCode
from hospital.models_flexible_pricing import PricingCategory, ServicePrice

print("=" * 80)
print("FINAL COMPREHENSIVE PRICING SYNC VERIFICATION")
print("=" * 80)
print()

all_services = ServiceCode.objects.filter(is_deleted=False)
total_services = all_services.count()

print(f"Total Services in System: {total_services}")
print()

# Get all categories
cash_categories = PricingCategory.objects.filter(category_type='cash', is_deleted=False)
corporate_categories = PricingCategory.objects.filter(category_type='corporate', is_deleted=False)
insurance_companies = InsuranceCompany.objects.filter(is_active=True, is_deleted=False).order_by('name')

print("=" * 80)
print("CASH CATEGORIES")
print("=" * 80)
print()

all_cash_synced = True
for cash_cat in cash_categories:
    service_count = ServicePrice.objects.filter(
        pricing_category=cash_cat,
        is_deleted=False
    ).values_list('service_code_id', flat=True).distinct().count()
    
    status = "✓" if service_count == total_services else "⚠️"
    print(f"{status} {cash_cat.name}: {service_count} / {total_services} services")
    if service_count != total_services:
        all_cash_synced = False

print()
print("=" * 80)
print("CORPORATE CATEGORIES")
print("=" * 80)
print()

all_corp_synced = True
for corp_cat in corporate_categories:
    service_count = ServicePrice.objects.filter(
        pricing_category=corp_cat,
        is_deleted=False
    ).values_list('service_code_id', flat=True).distinct().count()
    
    status = "✓" if service_count == total_services else "⚠️"
    print(f"{status} {corp_cat.name}: {service_count} / {total_services} services")
    if service_count != total_services:
        all_corp_synced = False

print()
print("=" * 80)
print("INSURANCE COMPANIES")
print("=" * 80)
print()

all_ins_synced = True
for ins_company in insurance_companies:
    pricing_cat = PricingCategory.objects.filter(
        insurance_company=ins_company,
        is_deleted=False
    ).first()
    
    if pricing_cat:
        service_count = ServicePrice.objects.filter(
            pricing_category=pricing_cat,
            is_deleted=False
        ).values_list('service_code_id', flat=True).distinct().count()
        
        status = "✓" if service_count == total_services else "⚠️"
        print(f"{status} {ins_company.name}: {service_count} / {total_services} services")
        if service_count != total_services:
            all_ins_synced = False
    else:
        print(f"✗ {ins_company.name}: No pricing category")
        all_ins_synced = False

print()
print("=" * 80)
print("STATISTICS")
print("=" * 80)
print()

total_price_entries = ServicePrice.objects.filter(is_deleted=False).count()
total_categories = cash_categories.count() + corporate_categories.count() + insurance_companies.count()

print(f"Total Price Entries: {total_price_entries:,}")
print(f"Total Categories: {total_categories}")
print(f"Expected Entries: {total_categories * total_services:,}")
print(f"Coverage: {(total_price_entries / (total_categories * total_services) * 100):.1f}%")
print()

print("=" * 80)
print("FINAL STATUS")
print("=" * 80)
print()

if all_cash_synced and all_corp_synced and all_ins_synced:
    print("✅ COMPLETE SYNC ACHIEVED!")
    print()
    print("Every service has pricing for:")
    print(f"  ✓ All {cash_categories.count()} cash category/categories")
    print(f"  ✓ All {corporate_categories.count()} corporate category/categories")
    print(f"  ✓ All {insurance_companies.count()} insurance companies")
    print()
    print("The system is ready for:")
    print("  ✓ Patient registration (all payment types)")
    print("  ✓ Automatic billing (all payer types)")
    print("  ✓ Invoice generation (all pricing categories)")
    print()
    print(f"Total: {total_price_entries:,} price entries ensuring complete coverage!")
else:
    print("⚠️  SOME CATEGORIES MAY STILL NEED ATTENTION")
    if not all_cash_synced:
        print("  - Cash categories need review")
    if not all_corp_synced:
        print("  - Corporate categories need review")
    if not all_ins_synced:
        print("  - Insurance companies need review")








