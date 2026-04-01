"""
Check Accounts Payable in General Ledger
Verify if AP balances were imported to GL and should be used instead
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting_advanced import AdvancedGeneralLedger
from hospital.models_accounting import Account
from django.db.models import Sum
from decimal import Decimal

print("=" * 80)
print("CHECKING ACCOUNTS PAYABLE IN GENERAL LEDGER")
print("=" * 80)

# Find all AP accounts
ap_accounts = Account.objects.filter(
    account_type='liability',
    is_deleted=False
).filter(
    account_name__icontains='payable'
).order_by('account_code')

print(f"\nFound {ap_accounts.count()} Accounts Payable accounts:")
for acc in ap_accounts:
    print(f"  - {acc.account_code}: {acc.account_name}")

# Check GL entries for each AP account
print(f"\n" + "=" * 80)
print("GENERAL LEDGER ENTRIES FOR AP ACCOUNTS:")
print("=" * 80)

total_ap_from_gl = Decimal('0.00')

for account in ap_accounts:
    gl_entries = AdvancedGeneralLedger.objects.filter(
        account=account,
        is_voided=False,
        is_deleted=False
    ).order_by('transaction_date')
    
    # For Excel imports: debit amounts ARE the balances (independent)
    # Sum all debit amounts (each is an independent balance)
    account_debit_total = gl_entries.aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
    account_credit_total = gl_entries.aggregate(total=Sum('credit_amount'))['total'] or Decimal('0.00')
    
    print(f"\n{account.account_code} - {account.account_name}:")
    print(f"  Total entries: {gl_entries.count()}")
    print(f"  Total Debits: GHS {account_debit_total:,.2f}")
    print(f"  Total Credits: GHS {account_credit_total:,.2f}")
    
    if gl_entries.count() > 0:
        print(f"\n  Sample entries:")
        for entry in gl_entries[:10]:
            balance_display = entry.debit_amount if entry.debit_amount > 0 else entry.credit_amount
            print(f"    - {entry.description[:60]}")
            print(f"      Date: {entry.transaction_date}, Debit: GHS {entry.debit_amount:,.2f}, Credit: GHS {entry.credit_amount:,.2f}")
            print(f"      Balance (from debit): GHS {balance_display:,.2f}")
    
    # For AP: if debit amounts are balances, use them
    # Otherwise, for liability accounts, balance = credits - debits
    if account_debit_total > 0:
        # Debit amounts are balances (from Excel import)
        account_balance = account_debit_total
    else:
        # Normal liability calculation
        account_balance = account_credit_total - account_debit_total
    
    total_ap_from_gl += account_balance
    print(f"  Account Balance: GHS {account_balance:,.2f}")

print(f"\n" + "=" * 80)
print("SUMMARY:")
print("=" * 80)
print(f"  Total AP from General Ledger: GHS {total_ap_from_gl:,.2f}")
print(f"  Total AP from AccountsPayable model: GHS 600,834.40")

if total_ap_from_gl > 0:
    print(f"\n  [INFO] General Ledger has AP entries")
    print(f"  [ACTION] Dashboard should use General Ledger if it has data")
else:
    print(f"\n  [INFO] General Ledger has no AP entries")
    print(f"  [INFO] Dashboard correctly using AccountsPayable model")

print("\n" + "=" * 80)
print("CHECK COMPLETE")
print("=" * 80)
