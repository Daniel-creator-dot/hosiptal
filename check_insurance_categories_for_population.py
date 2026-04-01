#!/usr/bin/env python
"""Check insurance categories to populate InsuranceCompany"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_flexible_pricing import PricingCategory, ServicePrice

print("=" * 80)
print("CHECKING INSURANCE CATEGORIES")
print("=" * 80)
print()

# Get all insurance pricing categories
insurance_categories = PricingCategory.objects.filter(
    category_type='insurance',
    is_deleted=False
)

print(f"Total insurance categories: {insurance_categories.count()}")
print()

for cat in insurance_categories:
    service_count = ServicePrice.objects.filter(
        pricing_category=cat,
        is_deleted=False
    ).count()
    
    # Extract company name
    company_name = cat.name.replace('Insurance - ', '').replace('Insurance ', '').strip()
    
    print(f"  {cat.name} ({cat.code})")
    print(f"    Type: {cat.category_type}")
    print(f"    Services: {service_count}")
    print(f"    Extracted name: '{company_name}'")
    print()








