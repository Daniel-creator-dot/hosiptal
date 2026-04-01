#!/usr/bin/env python
"""Add missing insurance companies to AccountingCorporateAccount"""
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
print("ADDING MISSING INSURANCE COMPANIES TO CORPORATE ACCOUNTS")
print("=" * 80)
print()

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

# Get all insurance pricing categories with pricing
insurance_categories = PricingCategory.objects.filter(
    category_type='insurance',
    is_deleted=False
)

# Filter to only those with services priced
categories_with_pricing = []
for cat in insurance_categories:
    service_count = ServicePrice.objects.filter(
        pricing_category=cat,
        is_deleted=False
    ).count()
    if service_count > 0:
        categories_with_pricing.append((cat, service_count))

print(f"Found {len(categories_with_pricing)} insurance companies with pricing:")
print()

added_count = 0
updated_count = 0

with transaction.atomic():
    for pricing_cat, service_count in categories_with_pricing:
        # Extract company name from category name
        company_name = pricing_cat.name.replace('Insurance - ', '').replace('Insurance ', '').strip()
        
        # Skip if it's too generic or invalid
        if company_name in ['(General)', 'cash / 100 Percent Mark-up', 'other  COMPANY(coperate)', 'INSURANCE', 'ORANGE INSURANCE']:
            continue
        
        # Generate account number
        account_number = f'CORP-{company_name.upper().replace(" ", "_").replace("-", "_")[:20]}'
        
        # Check if already exists
        existing = AccountingCorporateAccount.objects.filter(
            account_number=account_number,
            is_deleted=False
        ).first()
        
        if existing:
            # Update existing
            existing.company_name = company_name
            existing.receivable_account = ar_account
            existing.is_active = True
            existing.save()
            updated_count += 1
            print(f"✓ Updated: {account_number} - {company_name} ({service_count} services)")
        else:
            # Check if company name already exists (different account number)
            name_exists = AccountingCorporateAccount.objects.filter(
                company_name__iexact=company_name,
                is_deleted=False
            ).first()
            
            if name_exists:
                print(f"⚠️  Skipped: {company_name} (already exists as {name_exists.account_number})")
                continue
            
            # Create new
            account = AccountingCorporateAccount.objects.create(
                account_number=account_number,
                company_name=company_name,
                receivable_account=ar_account,
                credit_limit=Decimal('500000.00'),
                current_balance=Decimal('0.00'),
                is_active=True,
            )
            added_count += 1
            print(f"✓ Added: {account_number} - {company_name} ({service_count} services)")

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Added: {added_count} new insurance company accounts")
print(f"Updated: {updated_count} existing accounts")
print()

# Show all corporate accounts
print("All Corporate/Insurance Accounts:")
accounts = AccountingCorporateAccount.objects.filter(is_deleted=False).order_by('company_name')
for acc in accounts:
    # Find associated pricing
    pricing_cat = PricingCategory.objects.filter(
        name__icontains=acc.company_name,
        is_deleted=False
    ).first()
    
    if pricing_cat:
        service_count = ServicePrice.objects.filter(
            pricing_category=pricing_cat,
            is_deleted=False
        ).count()
        print(f"  ✓ {acc.account_number}: {acc.company_name} - {service_count} services priced")
    else:
        print(f"  - {acc.account_number}: {acc.company_name} (No pricing found)")

print()
print(f"Total: {accounts.count()} corporate/insurance accounts")
print()
print("✅ All insurance companies with pricing are now in AccountingCorporateAccount!")
print("   View at: http://192.168.2.216:8000/hms/accountant/corporate-accounts/")








