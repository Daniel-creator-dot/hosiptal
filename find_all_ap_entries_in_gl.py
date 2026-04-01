"""
Find All Accounts Payable Entries in General Ledger
Check all liability accounts for AP balances from Excel imports
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
print("FINDING ALL ACCOUNTS PAYABLE ENTRIES IN GENERAL LEDGER")
print("=" * 80)

# Find ALL liability accounts (AP is a liability)
liability_accounts = Account.objects.filter(
    account_type='liability',
    is_deleted=False
).order_by('account_code')

print(f"\nFound {liability_accounts.count()} liability accounts:")
for acc in liability_accounts:
    print(f"  - {acc.account_code}: {acc.account_name}")

# Check GL entries for each liability account
print(f"\n" + "=" * 80)
print("GENERAL LEDGER ENTRIES FOR LIABILITY ACCOUNTS:")
print("=" * 80)

total_ap_from_gl = Decimal('0.00')
ap_accounts_with_data = []

for account in liability_accounts:
    gl_entries = AdvancedGeneralLedger.objects.filter(
        account=account,
        is_voided=False,
        is_deleted=False
    ).order_by('transaction_date')
    
    # For Excel imports: debit amounts ARE the balances (independent)
    account_debit_total = gl_entries.aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
    account_credit_total = gl_entries.aggregate(total=Sum('credit_amount'))['total'] or Decimal('0.00')
    
    if gl_entries.count() > 0:
        print(f"\n{account.account_code} - {account.account_name}:")
        print(f"  Total entries: {gl_entries.count()}")
        print(f"  Total Debits: GHS {account_debit_total:,.2f}")
        print(f"  Total Credits: GHS {account_credit_total:,.2f}")
        
        # For Excel imports: debit amounts ARE the balances
        if account_debit_total > 0:
            account_balance = account_debit_total
            print(f"  Balance (from debit amounts): GHS {account_balance:,.2f}")
            total_ap_from_gl += account_balance
            ap_accounts_with_data.append({
                'account': account,
                'balance': account_balance,
                'entries': gl_entries.count()
            })
        
        # Show sample entries
        print(f"\n  Sample entries:")
        for entry in gl_entries[:5]:
            balance_display = entry.debit_amount if entry.debit_amount > 0 else entry.credit_amount
            print(f"    - {entry.description[:60]}")
            print(f"      Date: {entry.transaction_date}, Debit: GHS {entry.debit_amount:,.2f}, Credit: GHS {entry.credit_amount:,.2f}")

print(f"\n" + "=" * 80)
print("SUMMARY:")
print("=" * 80)
print(f"  Total AP from General Ledger (all liability accounts with debit balances): GHS {total_ap_from_gl:,.2f}")
print(f"  Accounts with data: {len(ap_accounts_with_data)}")

if len(ap_accounts_with_data) > 0:
    print(f"\n  Accounts with AP balances:")
    for item in ap_accounts_with_data:
        print(f"    - {item['account'].account_code}: {item['account'].account_name} = GHS {item['balance']:,.2f} ({item['entries']} entries)")

print("\n" + "=" * 80)
print("CHECK COMPLETE")
print("=" * 80)
