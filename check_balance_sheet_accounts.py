#!/usr/bin/env python
"""Check balance sheet accounts"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting import Account
from hospital.models_accounting_advanced import AdvancedGeneralLedger
from django.db.models import Sum
from decimal import Decimal

print("Checking Balance Sheet Accounts...")
print("=" * 80)

# Check Cash Account
cash = Account.objects.filter(account_code='1000').first()
if cash:
    print(f"✓ Cash Account (1000): {cash.account_name}")
    gl = AdvancedGeneralLedger.objects.filter(account=cash, is_voided=False).aggregate(
        d=Sum('debit_amount'), c=Sum('credit_amount')
    )
    balance = (gl['d'] or Decimal('0.00')) - (gl['c'] or Decimal('0.00'))
    print(f"  Balance: GHS {balance}")
else:
    print("✗ Cash Account (1000): NOT FOUND")

# Check Revenue Account
rev = Account.objects.filter(account_code='4000').first()
if rev:
    print(f"✓ Revenue Account (4000): {rev.account_name}")
    gl = AdvancedGeneralLedger.objects.filter(account=rev, is_voided=False).aggregate(
        d=Sum('debit_amount'), c=Sum('credit_amount')
    )
    balance = (gl['c'] or Decimal('0.00')) - (gl['d'] or Decimal('0.00'))
    print(f"  Balance: GHS {balance}")
else:
    print("✗ Revenue Account (4000): NOT FOUND")

print()
print("All Asset Accounts:")
assets = Account.objects.filter(account_type='asset', is_deleted=False).order_by('account_code')
for acc in assets[:10]:
    gl = AdvancedGeneralLedger.objects.filter(account=acc, is_voided=False).aggregate(
        d=Sum('debit_amount'), c=Sum('credit_amount')
    )
    balance = (gl['d'] or Decimal('0.00')) - (gl['c'] or Decimal('0.00'))
    print(f"  {acc.account_code}: {acc.account_name} - GHS {balance}")








