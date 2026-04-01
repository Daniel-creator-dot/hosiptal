"""
Verify fresh start - check that only Excel data remains
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting import Account, GeneralLedger
from decimal import Decimal

# Try to import AdvancedGeneralLedger
try:
    from hospital.models_accounting_advanced import AdvancedGeneralLedger
    HAS_ADVANCED = True
except ImportError:
    HAS_ADVANCED = False

print("=" * 80)
print("VERIFYING FRESH START")
print("Check that only Excel data (1200, 1201) remains")
print("=" * 80)

# Check Excel accounts
excel_accounts = ['1200', '1201']
print("\n1. Excel Accounts (Should have data):")
print("-" * 80)

for acc_code in excel_accounts:
    account = Account.objects.filter(account_code=acc_code, is_deleted=False).first()
    if account:
        gl_entries = GeneralLedger.objects.filter(account=account, is_deleted=False)
        if HAS_ADVANCED:
            adv_entries = AdvancedGeneralLedger.objects.filter(
                account=account, is_voided=False, is_deleted=False
            )
        else:
            adv_entries = []
        
        gl_debits = sum(e.debit_amount for e in gl_entries)
        gl_credits = sum(e.credit_amount for e in gl_entries)
        adv_debits = sum(e.debit_amount for e in adv_entries)
        adv_credits = sum(e.credit_amount for e in adv_entries)
        
        total_debits = gl_debits + adv_debits
        total_credits = gl_credits + adv_credits
        
        if account.account_type in ['asset', 'expense']:
            balance = total_debits - total_credits
        else:
            balance = total_credits - total_debits
        
        print(f"\n  {acc_code} - {account.account_name}")
        print(f"    GL entries: {gl_entries.count()}")
        print(f"    Adv entries: {adv_entries.count()}")
        print(f"    Balance: GHS {balance:,.2f}")
        print(f"    Status: {'OK' if (gl_entries.count() + adv_entries.count()) > 0 else 'EMPTY'}")

# Check revenue accounts
print("\n2. Revenue Accounts (Should be empty):")
print("-" * 80)

revenue_accounts = Account.objects.filter(account_type='revenue', is_deleted=False)[:5]
revenue_with_entries = 0

for account in revenue_accounts:
    gl_entries = GeneralLedger.objects.filter(account=account, is_deleted=False)
    if HAS_ADVANCED:
        adv_entries = AdvancedGeneralLedger.objects.filter(
            account=account, is_voided=False, is_deleted=False
        )
    else:
        adv_entries = []
    
    total_entries = gl_entries.count() + adv_entries.count()
    if total_entries > 0:
        revenue_with_entries += 1
        print(f"  [WARNING] {account.account_code} - {account.account_name}: {total_entries} entries")

if revenue_with_entries == 0:
    print("  [OK] All revenue accounts are empty")

# Check other accounts
print("\n3. Other Accounts (Should be empty):")
print("-" * 80)

other_accounts = Account.objects.filter(
    is_deleted=False
).exclude(
    account_code__in=excel_accounts
).exclude(
    account_type='revenue'
)[:10]

other_with_entries = 0

for account in other_accounts:
    gl_entries = GeneralLedger.objects.filter(account=account, is_deleted=False)
    if HAS_ADVANCED:
        adv_entries = AdvancedGeneralLedger.objects.filter(
            account=account, is_voided=False, is_deleted=False
        )
    else:
        adv_entries = []
    
    total_entries = gl_entries.count() + adv_entries.count()
    if total_entries > 0:
        other_with_entries += 1
        gl_debits = sum(e.debit_amount for e in gl_entries)
        gl_credits = sum(e.credit_amount for e in gl_entries)
        adv_debits = sum(e.debit_amount for e in adv_entries)
        adv_credits = sum(e.credit_amount for e in adv_entries)
        total_debits = gl_debits + adv_debits
        total_credits = gl_credits + adv_credits
        print(f"  [WARNING] {account.account_code} - {account.account_name}: {total_entries} entries (DR: {total_debits:,.2f}, CR: {total_credits:,.2f})")

if other_with_entries == 0:
    print("  [OK] All other accounts are empty")

print("\n" + "=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)

if revenue_with_entries == 0 and other_with_entries == 0:
    print("\n[OK] System is fresh - only Excel data (1200, 1201) has entries!")
else:
    print(f"\n[WARNING] Found {revenue_with_entries} revenue accounts and {other_with_entries} other accounts with entries")
