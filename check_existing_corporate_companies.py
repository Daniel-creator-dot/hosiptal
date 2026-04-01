#!/usr/bin/env python
"""Check for existing corporate companies with pricing"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Payer
from hospital.models_enterprise_billing import CorporateAccount
from hospital.models_flexible_pricing import PricingCategory, ServicePrice
from hospital.models_accounting_advanced import AccountingCorporateAccount

print("=" * 80)
print("CHECKING EXISTING CORPORATE COMPANIES WITH PRICING")
print("=" * 80)
print()

# Companies to check
companies = ['ECG', 'Melcom', 'Toyota', 'Alisa']

# 1. Check in Payers
print("1. CHECKING PAYERS:")
for company in companies:
    payers = Payer.objects.filter(
        name__icontains=company,
        is_deleted=False
    )
    if payers.exists():
        print(f"   ✓ {company} found in Payers:")
        for payer in payers:
            print(f"      - {payer.name} (Type: {payer.payer_type}, Active: {payer.is_active})")
    else:
        print(f"   ✗ {company} not found in Payers")
print()

# 2. Check in CorporateAccount (Enterprise Billing)
print("2. CHECKING ENTERPRISE CORPORATE ACCOUNTS:")
for company in companies:
    accounts = CorporateAccount.objects.filter(
        company_name__icontains=company,
        is_deleted=False
    )
    if accounts.exists():
        print(f"   ✓ {company} found in CorporateAccount:")
        for acc in accounts:
            print(f"      - {acc.company_code}: {acc.company_name}")
            print(f"        Credit Limit: GHS {acc.credit_limit}, Balance: GHS {acc.current_balance}")
            print(f"        Discount: {acc.global_discount_percentage}%")
            print(f"        Status: {acc.credit_status}, Active: {acc.is_active}")
    else:
        print(f"   ✗ {company} not found in CorporateAccount")
print()

# 3. Check in PricingCategory
print("3. CHECKING PRICING CATEGORIES:")
for company in companies:
    categories = PricingCategory.objects.filter(
        name__icontains=company,
        is_deleted=False
    )
    if categories.exists():
        print(f"   ✓ {company} found in PricingCategory:")
        for cat in categories:
            print(f"      - {cat.name} ({cat.code})")
            print(f"        Type: {cat.category_type}")
            # Count services with prices
            service_count = ServicePrice.objects.filter(
                pricing_category=cat,
                is_deleted=False
            ).count()
            print(f"        Services with prices: {service_count}")
    else:
        print(f"   ✗ {company} not found in PricingCategory")
print()

# 4. Check all Payers for corporate type
print("4. ALL CORPORATE PAYERS:")
corporate_payers = Payer.objects.filter(
    payer_type__icontains='corporate',
    is_deleted=False
)
print(f"   Found {corporate_payers.count()} corporate payers:")
for payer in corporate_payers:
    print(f"      - {payer.name} (Type: {payer.payer_type})")
print()

# 5. Check all PricingCategories for corporate type
print("5. ALL CORPORATE PRICING CATEGORIES:")
corporate_categories = PricingCategory.objects.filter(
    category_type='corporate',
    is_deleted=False
)
print(f"   Found {corporate_categories.count()} corporate pricing categories:")
for cat in corporate_categories:
    service_count = ServicePrice.objects.filter(
        pricing_category=cat,
        is_deleted=False
    ).count()
    print(f"      - {cat.name} ({cat.code}) - {service_count} services priced")
print()

# 6. Check AccountingCorporateAccount
print("6. ACCOUNTING CORPORATE ACCOUNTS:")
acc_accounts = AccountingCorporateAccount.objects.filter(is_deleted=False)
print(f"   Found {acc_accounts.count()} accounting corporate accounts:")
for acc in acc_accounts:
    print(f"      - {acc.account_number}: {acc.company_name}")
print()

# Summary
print("=" * 80)
print("SUMMARY")
print("=" * 80)

# Find which companies exist where
found_companies = {}
for company in companies:
    found_in = []
    
    # Check Payers
    if Payer.objects.filter(name__icontains=company, is_deleted=False).exists():
        found_in.append('Payers')
    
    # Check CorporateAccount
    if CorporateAccount.objects.filter(company_name__icontains=company, is_deleted=False).exists():
        found_in.append('CorporateAccount')
    
    # Check PricingCategory
    if PricingCategory.objects.filter(name__icontains=company, is_deleted=False).exists():
        found_in.append('PricingCategory')
    
    found_companies[company] = found_in

for company, locations in found_companies.items():
    if locations:
        print(f"✓ {company}: Found in {', '.join(locations)}")
    else:
        print(f"✗ {company}: Not found in system")

print()
print("To sync corporate accounts with pricing, we may need to:")
print("  1. Link existing Payers/PricingCategories to AccountingCorporateAccount")
print("  2. Or create AccountingCorporateAccount from existing data")








