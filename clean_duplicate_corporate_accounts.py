#!/usr/bin/env python
"""Clean duplicate corporate accounts"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import transaction
from hospital.models_accounting_advanced import AccountingCorporateAccount
from hospital.models_flexible_pricing import PricingCategory

print("=" * 80)
print("CLEANING DUPLICATE CORPORATE ACCOUNTS")
print("=" * 80)
print()

# Find duplicates
accounts = AccountingCorporateAccount.objects.filter(is_deleted=False).order_by('company_name')

# Group by similar names
duplicates = {}
for acc in accounts:
    name_key = acc.company_name.upper().replace(' ', '').replace('-', '').replace('_', '')
    if name_key not in duplicates:
        duplicates[name_key] = []
    duplicates[name_key].append(acc)

removed_count = 0

with transaction.atomic():
    for name_key, acc_list in duplicates.items():
        if len(acc_list) > 1:
            # Keep the one with more complete name or better account number
            acc_list.sort(key=lambda x: (len(x.company_name), x.account_number))
            keep = acc_list[-1]  # Keep the last one (most complete)
            remove = acc_list[:-1]  # Remove others
            
            print(f"Found duplicates for '{name_key}':")
            print(f"  Keeping: {keep.account_number} - {keep.company_name}")
            
            for acc in remove:
                print(f"  Removing: {acc.account_number} - {acc.company_name}")
                acc.is_deleted = True
                acc.save()
                removed_count += 1
            print()

print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Removed: {removed_count} duplicate accounts")
print()

# Show final list
print("Final Corporate/Insurance Accounts:")
accounts = AccountingCorporateAccount.objects.filter(is_deleted=False).order_by('company_name')
for acc in accounts:
    pricing_cat = PricingCategory.objects.filter(
        name__icontains=acc.company_name,
        is_deleted=False
    ).first()
    
    if pricing_cat:
        from hospital.models_flexible_pricing import ServicePrice
        service_count = ServicePrice.objects.filter(
            pricing_category=pricing_cat,
            is_deleted=False
        ).count()
        print(f"  ✓ {acc.account_number}: {acc.company_name} - {service_count} services")
    else:
        print(f"  - {acc.account_number}: {acc.company_name}")

print()
print(f"Total: {accounts.count()} corporate/insurance accounts")








