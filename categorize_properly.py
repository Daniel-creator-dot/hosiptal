#!/usr/bin/env python
"""Properly categorize insurance companies, corporate accounts, and cash"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_flexible_pricing import PricingCategory, ServicePrice
from hospital.models_accounting_advanced import AccountingCorporateAccount
from hospital.models_accounting import Account
from decimal import Decimal

print("=" * 80)
print("PROPERLY CATEGORIZING: INSURANCE vs CORPORATE vs CASH")
print("=" * 80)
print()

# Define proper categories
INSURANCE_COMPANIES = [
    'ACE', 'GHIC', 'GLICO', 'GRIDCO', 'MEDICALS', 'METROPOLITAN', 
    'NATIONWIDE', 'PREMIER', 'FOREIGNER', 'WALK-IN SERVICES'
]

CORPORATE_COMPANIES = [
    'ECG', 'MELCOM', 'TOYOTA GHANA', 'ALISA HOTEL'
]

CASH_CATEGORIES = [
    'CASH', 'Cash'
]

print("CATEGORIZATION LOGIC:")
print()
print("INSURANCE COMPANIES (Insurance providers):")
for ins in INSURANCE_COMPANIES:
    print(f"  - {ins}")
print()

print("CORPORATE ACCOUNTS (Corporate clients):")
for corp in CORPORATE_COMPANIES:
    print(f"  - {corp}")
print()

print("CASH (Cash payments):")
for cash in CASH_CATEGORIES:
    print(f"  - {cash}")
print()

# Get all pricing categories
all_categories = PricingCategory.objects.filter(is_deleted=False)

print("=" * 80)
print("CHECKING CURRENT PRICING CATEGORIES")
print("=" * 80)
print()

insurance_cats = []
corporate_cats = []
cash_cats = []
other_cats = []

for cat in all_categories:
    cat_name_upper = cat.name.upper()
    
    # Check if insurance
    is_insurance = False
    for ins in INSURANCE_COMPANIES:
        if ins.upper() in cat_name_upper:
            is_insurance = True
            break
    
    # Check if corporate
    is_corporate = False
    for corp in CORPORATE_COMPANIES:
        if corp.upper() in cat_name_upper:
            is_corporate = True
            break
    
    # Check if cash
    is_cash = False
    for cash in CASH_CATEGORIES:
        if cash.upper() in cat_name_upper or 'CASH' in cat_name_upper:
            is_cash = True
            break
    
    service_count = ServicePrice.objects.filter(
        pricing_category=cat,
        is_deleted=False
    ).count()
    
    if is_insurance:
        insurance_cats.append((cat, service_count))
    elif is_corporate:
        corporate_cats.append((cat, service_count))
    elif is_cash:
        cash_cats.append((cat, service_count))
    else:
        other_cats.append((cat, service_count))

print("INSURANCE CATEGORIES:")
for cat, count in insurance_cats:
    print(f"  ✓ {cat.name} ({cat.code}) - Type: {cat.category_type} - {count} services")
    if cat.category_type != 'insurance':
        print(f"    ⚠️  Should be 'insurance' type but is '{cat.category_type}'")
print()

print("CORPORATE CATEGORIES:")
for cat, count in corporate_cats:
    print(f"  ✓ {cat.name} ({cat.code}) - Type: {cat.category_type} - {count} services")
    if cat.category_type != 'corporate':
        print(f"    ⚠️  Should be 'corporate' type but is '{cat.category_type}'")
print()

print("CASH CATEGORIES:")
for cat, count in cash_cats:
    print(f"  ✓ {cat.name} ({cat.code}) - Type: {cat.category_type} - {count} services")
    if cat.category_type != 'cash':
        print(f"    ⚠️  Should be 'cash' type but is '{cat.category_type}'")
print()

print("OTHER CATEGORIES:")
for cat, count in other_cats:
    print(f"  - {cat.name} ({cat.code}) - Type: {cat.category_type} - {count} services")
print()

print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Insurance Categories: {len(insurance_cats)}")
print(f"Corporate Categories: {len(corporate_cats)}")
print(f"Cash Categories: {len(cash_cats)}")
print(f"Other Categories: {len(other_cats)}")
print()

# Check AccountingCorporateAccount
print("ACCOUNTING CORPORATE ACCOUNTS:")
acc_accounts = AccountingCorporateAccount.objects.filter(is_deleted=False)
print(f"  Found {acc_accounts.count()} accounts:")
for acc in acc_accounts:
    # Determine if it's actually insurance or corporate
    is_insurance = any(ins.upper() in acc.company_name.upper() for ins in INSURANCE_COMPANIES)
    is_corporate = any(corp.upper() in acc.company_name.upper() for corp in CORPORATE_COMPANIES)
    
    if is_insurance:
        print(f"    ⚠️  {acc.account_number}: {acc.company_name} - Should be in INSURANCE, not CORPORATE")
    elif is_corporate:
        print(f"    ✓ {acc.account_number}: {acc.company_name} - Correctly in CORPORATE")
    else:
        print(f"    ? {acc.account_number}: {acc.company_name} - Unknown category")








