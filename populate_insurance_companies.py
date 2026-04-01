#!/usr/bin/env python
"""Populate InsuranceCompany model from existing insurance pricing categories"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import transaction
from hospital.models_insurance_companies import InsuranceCompany
from hospital.models_flexible_pricing import PricingCategory, ServicePrice

print("=" * 80)
print("POPULATING INSURANCE COMPANY MODEL")
print("=" * 80)
print()

# Get all insurance pricing categories (excluding general and invalid ones)
insurance_categories = PricingCategory.objects.filter(
    category_type='insurance',
    is_deleted=False
).exclude(
    name__icontains='cash'
).exclude(
    name__icontains='other company'
).exclude(
    name__icontains='(General)'
).exclude(
    code='INSURANCE'  # Exclude generic "Insurance (General)"
).exclude(
    code='INS_INSURANCE'  # Exclude "Insurance - INSURANCE"
).exclude(
    code='INS_ORANGE_INSURANCE'  # Exclude "Insurance - ORANGE INSURANCE" (0 services)
)

print(f"Found {insurance_categories.count()} insurance pricing categories to process:")
print()

created_count = 0
updated_count = 0

with transaction.atomic():
    for pricing_cat in insurance_categories:
        # Extract company name from category name
        # Format: "Insurance - ACE" -> "ACE"
        company_name = pricing_cat.name.replace('Insurance - ', '').replace('Insurance ', '').strip()
        
        # Skip if empty or invalid
        if not company_name or company_name in ['(General)', 'INSURANCE', 'cash / 100 Percent Mark-up', 'other  COMPANY(coperate)']:
            continue
        
        # Get service count
        service_count = ServicePrice.objects.filter(
            pricing_category=pricing_cat,
            is_deleted=False
        ).count()
        
        # Skip if no services
        if service_count == 0:
            print(f"  Skipping: {company_name} (no services)")
            continue
        
        # Generate code from category code or company name
        # Format: "INS_ACE" -> "ACE"
        if pricing_cat.code.startswith('INS_'):
            company_code = pricing_cat.code.replace('INS_', '').upper()
        else:
            # Generate from company name
            company_code = company_name.upper().replace(' ', '_').replace('-', '_')[:20]
        
        # Check if insurance company already exists
        existing = InsuranceCompany.objects.filter(
            code=company_code,
            is_deleted=False
        ).first()
        
        if not existing:
            # Check by name
            existing = InsuranceCompany.objects.filter(
                name__iexact=company_name,
                is_deleted=False
            ).first()
        
        if existing:
            # Update existing
            existing.name = company_name
            existing.code = company_code
            existing.is_active = True
            existing.status = 'active'
            existing.save()
            updated_count += 1
            print(f"✓ Updated: {company_name} ({company_code}) - {service_count} services")
        else:
            # Create new
            insurance_company = InsuranceCompany.objects.create(
                name=company_name,
                code=company_code,
                is_active=True,
                status='active',
                payment_terms_days=30,
            )
            created_count += 1
            print(f"✓ Created: {company_name} ({company_code}) - {service_count} services")

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Created: {created_count} new insurance companies")
print(f"Updated: {updated_count} existing insurance companies")
print()

# Show all insurance companies
print("ALL INSURANCE COMPANIES:")
insurance_companies = InsuranceCompany.objects.filter(is_deleted=False).order_by('name')
print(f"Total: {insurance_companies.count()} companies")
print()
for ins in insurance_companies:
    # Find associated pricing category
    pricing_cat = PricingCategory.objects.filter(
        name__icontains=ins.name,
        category_type='insurance',
        is_deleted=False
    ).first()
    
    if pricing_cat:
        service_count = ServicePrice.objects.filter(
            pricing_category=pricing_cat,
            is_deleted=False
        ).count()
        print(f"  ✓ {ins.name} ({ins.code}) - {service_count} services priced")
        print(f"      Status: {ins.status}, Active: {ins.is_active}")
    else:
        print(f"  ⚠️  {ins.name} ({ins.code}) - No pricing category found")
        print(f"      Status: {ins.status}, Active: {ins.is_active}")

print()
print("✅ Insurance companies populated!")
print("   View at: http://192.168.2.216:8000/admin/hospital/insurancecompany/")

