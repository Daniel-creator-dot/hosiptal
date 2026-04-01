#!/usr/bin/env python
"""Sync corporate accounts with existing pricing categories"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import transaction
from hospital.models_accounting_advanced import AccountingCorporateAccount
from hospital.models_flexible_pricing import PricingCategory, ServicePrice
from hospital.models_accounting import Account
from decimal import Decimal

print("=" * 80)
print("SYNCING CORPORATE ACCOUNTS WITH EXISTING PRICING")
print("=" * 80)
print()

# Mapping of company names to pricing category codes
company_mapping = {
    'ECG': 'INS_ECG',
    'Melcom': 'INS_MELCOM',
    'Toyota': 'INS_TOYOTA_GHANA',
    'Alisa': 'INS_ALISA_HOTEL',
}

# Get Accounts Receivable account
ar_account = Account.objects.filter(
    account_code='1200',
    is_deleted=False
).first()

if not ar_account:
    ar_account = Account.objects.create(
        account_code='1200',
        account_name='Accounts Receivable',
        account_type='asset',
        is_active=True
    )

updated_count = 0

with transaction.atomic():
    for company_name, pricing_code in company_mapping.items():
        # Find pricing category
        pricing_category = PricingCategory.objects.filter(
            code=pricing_code,
            is_deleted=False
        ).first()
        
        if not pricing_category:
            print(f"⚠️  Pricing category {pricing_code} not found for {company_name}")
            continue
        
        # Count services with prices
        service_count = ServicePrice.objects.filter(
            pricing_category=pricing_category,
            is_deleted=False
        ).count()
        
        print(f"✓ Found pricing for {company_name}:")
        print(f"    Category: {pricing_category.name} ({pricing_category.code})")
        print(f"    Services with prices: {service_count}")
        
        # Find or create AccountingCorporateAccount
        account_number = f'CORP-{company_name.upper()}'
        corp_account = AccountingCorporateAccount.objects.filter(
            account_number=account_number,
            is_deleted=False
        ).first()
        
        if corp_account:
            # Update with pricing info
            corp_account.company_name = company_name
            corp_account.receivable_account = ar_account
            corp_account.is_active = True
            # Set credit limit based on pricing category if available
            if service_count > 0:
                # Estimate credit limit (can be adjusted)
                corp_account.credit_limit = Decimal('500000.00')
            corp_account.save()
            updated_count += 1
            print(f"    ✓ Updated AccountingCorporateAccount: {account_number}")
        else:
            # Create new
            corp_account = AccountingCorporateAccount.objects.create(
                account_number=account_number,
                company_name=company_name,
                receivable_account=ar_account,
                credit_limit=Decimal('500000.00'),
                current_balance=Decimal('0.00'),
                is_active=True,
            )
            updated_count += 1
            print(f"    ✓ Created AccountingCorporateAccount: {account_number}")
        
        print()

print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"✓ Synced {updated_count} corporate accounts with pricing")
print()

# Show final status
print("Corporate Accounts with Pricing:")
accounts = AccountingCorporateAccount.objects.filter(is_deleted=False).order_by('company_name')
for acc in accounts:
    # Find associated pricing category
    pricing_cat = None
    for code in company_mapping.values():
        if code in [f'INS_{acc.company_name.upper()}', f'INS_{acc.company_name.upper()}_GHANA', f'INS_{acc.company_name.upper()}_HOTEL']:
            pricing_cat = PricingCategory.objects.filter(code=code, is_deleted=False).first()
            break
    
    if not pricing_cat:
        # Try direct match
        pricing_cat = PricingCategory.objects.filter(
            name__icontains=acc.company_name,
            is_deleted=False
        ).first()
    
    if pricing_cat:
        service_count = ServicePrice.objects.filter(
            pricing_category=pricing_cat,
            is_deleted=False
        ).count()
        print(f"  ✓ {acc.account_number}: {acc.company_name}")
        print(f"    Pricing: {pricing_cat.name} - {service_count} services priced")
    else:
        print(f"  ⚠️  {acc.account_number}: {acc.company_name} (No pricing category linked)")

print()
print("✅ Corporate accounts are now synced with their pricing!")
print("   View at: http://192.168.2.216:8000/hms/accountant/corporate-accounts/")








