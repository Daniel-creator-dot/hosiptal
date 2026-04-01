#!/usr/bin/env python
"""Fix categorization: Update PricingCategory types and remove insurance from corporate accounts"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import transaction
from hospital.models_flexible_pricing import PricingCategory, ServicePrice
from hospital.models_accounting_advanced import AccountingCorporateAccount

print("=" * 80)
print("FIXING CATEGORIZATION: INSURANCE vs CORPORATE vs CASH")
print("=" * 80)
print()

# Define proper categories
CORPORATE_COMPANIES = ['ECG', 'MELCOM', 'TOYOTA GHANA', 'ALISA HOTEL']
INSURANCE_COMPANIES = ['ACE', 'GHIC', 'GLICO', 'GRIDCO', 'MEDICALS', 'METROPOLITAN', 
                       'NATIONWIDE', 'PREMIER', 'FOREIGNER', 'WALK-IN SERVICES']

updated_count = 0
removed_count = 0

with transaction.atomic():
    # 1. Fix PricingCategory types for corporate companies
    print("1. FIXING PRICING CATEGORY TYPES:")
    print()
    
    for corp_name in CORPORATE_COMPANIES:
        # Find the pricing category
        cat = PricingCategory.objects.filter(
            name__icontains=corp_name,
            is_deleted=False
        ).first()
        
        if cat and cat.category_type != 'corporate':
            print(f"   Updating: {cat.name} ({cat.code})")
            print(f"      From: {cat.category_type} → To: corporate")
            cat.category_type = 'corporate'
            cat.save()
            updated_count += 1
        elif cat:
            print(f"   ✓ Already correct: {cat.name} ({cat.code}) - {cat.category_type}")
    
    print()
    
    # 2. Remove insurance companies from AccountingCorporateAccount
    print("2. REMOVING INSURANCE COMPANIES FROM CORPORATE ACCOUNTS:")
    print()
    
    for ins_name in INSURANCE_COMPANIES:
        accounts = AccountingCorporateAccount.objects.filter(
            company_name__iexact=ins_name,
            is_deleted=False
        )
        
        for acc in accounts:
            print(f"   Removing: {acc.account_number} - {acc.company_name} (Insurance company)")
            acc.is_deleted = True
            acc.save()
            removed_count += 1
    
    print()
    
    # 3. Verify corporate accounts match pricing categories
    print("3. VERIFYING CORPORATE ACCOUNTS:")
    print()
    
    corporate_accounts = AccountingCorporateAccount.objects.filter(is_deleted=False)
    for acc in corporate_accounts:
        # Find matching pricing category
        pricing_cat = PricingCategory.objects.filter(
            name__icontains=acc.company_name,
            category_type='corporate',
            is_deleted=False
        ).first()
        
        if pricing_cat:
            service_count = ServicePrice.objects.filter(
                pricing_category=pricing_cat,
                is_deleted=False
            ).count()
            print(f"   ✓ {acc.account_number}: {acc.company_name}")
            print(f"      Pricing: {pricing_cat.name} ({pricing_cat.code}) - {service_count} services")
        else:
            print(f"   ⚠️  {acc.account_number}: {acc.company_name} (No corporate pricing category found)")
    
    print()

print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Updated PricingCategory types: {updated_count}")
print(f"Removed insurance companies from corporate accounts: {removed_count}")
print()

# Show final state
print("FINAL STATE:")
print()

print("CORPORATE ACCOUNTS (AccountingCorporateAccount):")
corp_accounts = AccountingCorporateAccount.objects.filter(is_deleted=False).order_by('company_name')
for acc in corp_accounts:
    # Find matching pricing category
    pricing_cat = PricingCategory.objects.filter(
        name__icontains=acc.company_name,
        category_type='corporate',
        is_deleted=False
    ).first()
    
    if pricing_cat:
        service_count = ServicePrice.objects.filter(
            pricing_category=pricing_cat,
            is_deleted=False
        ).count()
        print(f"  ✓ {acc.account_number}: {acc.company_name}")
        print(f"      Pricing: {pricing_cat.name} ({pricing_cat.category_type}) - {service_count} services")
    else:
        print(f"  ⚠️  {acc.account_number}: {acc.company_name} (No pricing linked)")
print()

print("CORPORATE PRICING CATEGORIES:")
corp_cats = PricingCategory.objects.filter(
    category_type='corporate',
    is_deleted=False
)
for cat in corp_cats:
    service_count = ServicePrice.objects.filter(
        pricing_category=cat,
        is_deleted=False
    ).count()
    print(f"  ✓ {cat.name} ({cat.code}) - {service_count} services")
print()

print("INSURANCE PRICING CATEGORIES:")
ins_cats = PricingCategory.objects.filter(
    category_type='insurance',
    is_deleted=False
).exclude(name__icontains='cash').exclude(name__icontains='other company')
for cat in ins_cats:
    service_count = ServicePrice.objects.filter(
        pricing_category=cat,
        is_deleted=False
    ).count()
    if service_count > 0:
        print(f"  ✓ {cat.name} ({cat.code}) - {service_count} services")
print()

print("CASH PRICING CATEGORIES:")
cash_cats = PricingCategory.objects.filter(
    category_type='cash',
    is_deleted=False
)
for cat in cash_cats:
    service_count = ServicePrice.objects.filter(
        pricing_category=cat,
        is_deleted=False
    ).count()
    print(f"  ✓ {cat.name} ({cat.code}) - {service_count} services")
print()

print("✅ Categorization fixed!")

