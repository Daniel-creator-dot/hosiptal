#!/usr/bin/env python
"""Debug balance sheet values"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from hospital.views_accounting_advanced import balance_sheet
from decimal import Decimal

factory = RequestFactory()
request = factory.get('/accounting/balance-sheet/')
user = User.objects.filter(is_superuser=True).first() or User.objects.first()
request.user = user

# Simulate the view
from django.utils import timezone
from hospital.models_accounting import Account
from hospital.models_accounting_advanced import AdvancedGeneralLedger
from django.db.models import Sum
from datetime import datetime

as_of_date = timezone.now().date()

def get_account_balance(account_code, account_type='asset', as_of_date=None):
    """Get balance for a specific account"""
    try:
        account = Account.objects.get(account_code=account_code, is_deleted=False)
    except Account.DoesNotExist:
        return Decimal('0.00')
    
    ledger_sum = AdvancedGeneralLedger.objects.filter(
        account=account,
        transaction_date__lte=as_of_date,
        is_voided=False
    ).aggregate(
        debits=Sum('debit_amount'),
        credits=Sum('credit_amount')
    )
    
    # Handle None values from aggregate
    debits = Decimal(str(ledger_sum['debits'])) if ledger_sum['debits'] is not None else Decimal('0.00')
    credits = Decimal(str(ledger_sum['credits'])) if ledger_sum['credits'] is not None else Decimal('0.00')
    
    if account_type in ['asset', 'expense']:
        balance = debits - credits
    else:
        balance = credits - debits
    
    # Ensure we return a Decimal
    return Decimal(str(balance)) if balance is not None else Decimal('0.00')

# ASSETS - Build dictionary structure
assets = {
    'cash': Decimal('0.00'),
    'bank': Decimal('0.00'),
    'accounts_receivable': Decimal('0.00'),
    'inventory': Decimal('0.00'),
    'prepaid': Decimal('0.00'),
    'equipment': Decimal('0.00'),
    'building': Decimal('0.00'),
    'depreciation': Decimal('0.00'),
}

# Map account codes to asset categories
# Cash accounts (1000-1099)
cash_accounts = Account.objects.filter(
    account_type='asset',
    account_code__startswith='10',
    is_deleted=False
)

print("Cash Accounts Found:")
for account in cash_accounts:
    print(f"  {account.account_code}: {account.account_name}")
    balance = get_account_balance(account.account_code, 'asset', as_of_date)
    print(f"    Balance: {balance} (type: {type(balance)})")
    
    account_name_lower = (account.account_name or '').lower()
    account_code = account.account_code or ''
    
    if account_code in ['1000', '1010'] or 'cash' in account_name_lower:
        assets['cash'] += balance
        print(f"    -> Added to cash: {balance}")
    elif account_code.startswith('102') or 'bank' in account_name_lower:
        assets['bank'] += balance
        print(f"    -> Added to bank: {balance}")

print()
print("Final Assets Dictionary:")
for key, value in assets.items():
    print(f"  {key}: {value} (type: {type(value)})")
    # Check if it can be formatted
    try:
        formatted = f"{value:.2f}"
        print(f"    -> Can format: {formatted}")
    except Exception as e:
        print(f"    -> ERROR formatting: {e}")








