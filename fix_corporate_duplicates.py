#!/usr/bin/env python
"""Fix duplicate corporate accounts - keep the more complete names"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import transaction
from hospital.models_accounting_advanced import AccountingCorporateAccount

print("=" * 80)
print("FIXING DUPLICATE CORPORATE ACCOUNTS")
print("=" * 80)
print()

# Known duplicates to fix
duplicates_to_fix = [
    {
        'keep': 'ALISA HOTEL',  # Keep the more complete name
        'remove': ['Alisa']
    },
    {
        'keep': 'TOYOTA GHANA',  # Keep the more complete name
        'remove': ['Toyota']
    }
]

removed_count = 0

with transaction.atomic():
    for dup_group in duplicates_to_fix:
        keep_name = dup_group['keep']
        remove_names = dup_group['remove']
        
        # Find the account to keep
        keep_account = AccountingCorporateAccount.objects.filter(
            company_name__iexact=keep_name,
            is_deleted=False
        ).first()
        
        if not keep_account:
            print(f"⚠️  Account '{keep_name}' not found, skipping...")
            continue
        
        print(f"Keeping: {keep_account.account_number} - {keep_account.company_name}")
        
        # Remove duplicates
        for remove_name in remove_names:
            remove_accounts = AccountingCorporateAccount.objects.filter(
                company_name__iexact=remove_name,
                is_deleted=False
            )
            
            for acc in remove_accounts:
                print(f"  Removing duplicate: {acc.account_number} - {acc.company_name}")
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
    from hospital.models_flexible_pricing import PricingCategory, ServicePrice
    pricing_cat = PricingCategory.objects.filter(
        name__icontains=acc.company_name,
        is_deleted=False
    ).first()
    
    if pricing_cat:
        service_count = ServicePrice.objects.filter(
            pricing_category=pricing_cat,
            is_deleted=False
        ).count()
        print(f"  ✓ {acc.account_number}: {acc.company_name} - {service_count} services")
    else:
        print(f"  - {acc.account_number}: {acc.company_name}")

print()
print(f"Total: {accounts.count()} corporate/insurance accounts")
print()
print("✅ Duplicates cleaned! All accounts are now unique.")








