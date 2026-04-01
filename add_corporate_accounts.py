#!/usr/bin/env python
"""Add corporate accounts: ECG, Melcom, Toyota, Alisa"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import transaction
from hospital.models_accounting_advanced import AccountingCorporateAccount
from hospital.models_accounting import Account
from decimal import Decimal

print("=" * 80)
print("ADDING CORPORATE ACCOUNTS")
print("=" * 80)
print()

# Get or create Accounts Receivable account
ar_account, created = Account.objects.get_or_create(
    account_code='1200',
    defaults={
        'account_name': 'Accounts Receivable',
        'account_type': 'asset',
        'is_active': True
    }
)

if created:
    print(f"✓ Created Accounts Receivable account: {ar_account.account_code}")
else:
    print(f"✓ Using existing Accounts Receivable account: {ar_account.account_code}")
print()

# Corporate accounts to add
corporate_accounts = [
    {
        'account_number': 'CORP-ECG',
        'company_name': 'ECG',
        'contact_person': 'ECG Accounts Department',
        'contact_email': 'accounts@ecg.com.gh',
        'contact_phone': '',
        'credit_limit': Decimal('500000.00'),
        'current_balance': Decimal('0.00'),
    },
    {
        'account_number': 'CORP-MELCOM',
        'company_name': 'Melcom',
        'contact_person': 'Melcom Accounts Department',
        'contact_email': 'accounts@melcom.com.gh',
        'contact_phone': '',
        'credit_limit': Decimal('500000.00'),
        'current_balance': Decimal('0.00'),
    },
    {
        'account_number': 'CORP-TOYOTA',
        'company_name': 'Toyota',
        'contact_person': 'Toyota Accounts Department',
        'contact_email': 'accounts@toyota.com.gh',
        'contact_phone': '',
        'credit_limit': Decimal('500000.00'),
        'current_balance': Decimal('0.00'),
    },
    {
        'account_number': 'CORP-ALISA',
        'company_name': 'Alisa',
        'contact_person': 'Alisa Accounts Department',
        'contact_email': 'accounts@alisa.com.gh',
        'contact_phone': '',
        'credit_limit': Decimal('500000.00'),
        'current_balance': Decimal('0.00'),
    },
]

added_count = 0
updated_count = 0

with transaction.atomic():
    for corp_data in corporate_accounts:
        account_number = corp_data['account_number']
        company_name = corp_data['company_name']
        
        # Check if exists
        existing = AccountingCorporateAccount.objects.filter(
            account_number=account_number,
            is_deleted=False
        ).first()
        
        if existing:
            # Update existing
            existing.company_name = company_name
            existing.contact_person = corp_data['contact_person']
            existing.contact_email = corp_data['contact_email']
            existing.contact_phone = corp_data['contact_phone']
            existing.credit_limit = corp_data['credit_limit']
            existing.receivable_account = ar_account
            existing.is_active = True
            existing.save()
            updated_count += 1
            print(f"✓ Updated: {account_number} - {company_name}")
        else:
            # Create new
            account = AccountingCorporateAccount.objects.create(
                account_number=account_number,
                company_name=company_name,
                contact_person=corp_data['contact_person'],
                contact_email=corp_data['contact_email'],
                contact_phone=corp_data['contact_phone'],
                credit_limit=corp_data['credit_limit'],
                current_balance=corp_data['current_balance'],
                receivable_account=ar_account,
                is_active=True,
            )
            added_count += 1
            print(f"✓ Added: {account_number} - {company_name}")

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Added: {added_count} new corporate accounts")
print(f"Updated: {updated_count} existing corporate accounts")
print()
print("Corporate accounts now available:")
accounts = AccountingCorporateAccount.objects.filter(is_deleted=False).order_by('company_name')
for acc in accounts:
    print(f"  - {acc.account_number}: {acc.company_name} (Credit Limit: GHS {acc.credit_limit:,.2f})")
print()
print("✅ Corporate accounts are now visible at:")
print("   http://192.168.2.216:8000/hms/accountant/corporate-accounts/")








