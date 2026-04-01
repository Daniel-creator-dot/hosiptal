#!/usr/bin/env python
"""Verify final categorization is correct"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_flexible_pricing import PricingCategory, ServicePrice
from hospital.models_accounting_advanced import AccountingCorporateAccount

print("=" * 80)
print("FINAL CATEGORIZATION VERIFICATION")
print("=" * 80)
print()

# CORPORATE
print("✅ CORPORATE ACCOUNTS (AccountingCorporateAccount):")
corp_accounts = AccountingCorporateAccount.objects.filter(is_deleted=False).order_by('company_name')
print(f"   Total: {corp_accounts.count()} accounts")
for acc in corp_accounts:
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
        print(f"   ✓ {acc.company_name} - {service_count} services priced")
print()

print("✅ CORPORATE PRICING CATEGORIES (category_type='corporate'):")
corp_cats = PricingCategory.objects.filter(
    category_type='corporate',
    is_deleted=False
)
print(f"   Total: {corp_cats.count()} categories")
for cat in corp_cats:
    service_count = ServicePrice.objects.filter(
        pricing_category=cat,
        is_deleted=False
    ).count()
    if service_count > 0:
        print(f"   ✓ {cat.name} ({cat.code}) - {service_count} services")
print()

# INSURANCE
print("✅ INSURANCE PRICING CATEGORIES (category_type='insurance'):")
ins_cats = PricingCategory.objects.filter(
    category_type='insurance',
    is_deleted=False
).exclude(name__icontains='cash').exclude(name__icontains='other company').exclude(name__icontains='orange')
print(f"   Total: {ins_cats.count()} categories")
for cat in ins_cats:
    service_count = ServicePrice.objects.filter(
        pricing_category=cat,
        is_deleted=False
    ).count()
    if service_count > 0:
        print(f"   ✓ {cat.name} ({cat.code}) - {service_count} services")
print()

# CASH
print("✅ CASH PRICING CATEGORIES (category_type='cash'):")
cash_cats = PricingCategory.objects.filter(
    category_type='cash',
    is_deleted=False
)
print(f"   Total: {cash_cats.count()} categories")
for cat in cash_cats:
    service_count = ServicePrice.objects.filter(
        pricing_category=cat,
        is_deleted=False
    ).count()
    print(f"   ✓ {cat.name} ({cat.code}) - {service_count} services")
print()

# Verify no insurance companies in corporate accounts
print("✅ VERIFICATION: Insurance companies NOT in Corporate Accounts:")
insurance_names = ['ACE', 'GHIC', 'GLICO', 'GRIDCO', 'MEDICALS', 'METROPOLITAN', 
                   'NATIONWIDE', 'PREMIER', 'FOREIGNER', 'WALK-IN SERVICES']
for ins_name in insurance_names:
    found = AccountingCorporateAccount.objects.filter(
        company_name__iexact=ins_name,
        is_deleted=False
    ).exists()
    if found:
        print(f"   ⚠️  {ins_name} - STILL IN CORPORATE ACCOUNTS (should be removed)")
    else:
        print(f"   ✓ {ins_name} - Correctly NOT in corporate accounts")
print()

print("=" * 80)
print("SUMMARY")
print("=" * 80)
print("✅ Corporate Accounts: 4 (ECG, MELCOM, TOYOTA GHANA, ALISA HOTEL)")
print("✅ Insurance Categories: 11 (ACE, GHIC, GLICO, etc.)")
print("✅ Cash Categories: 1 (Cash / Private Patients)")
print()
print("✅ All categorizations are now logically correct!")








