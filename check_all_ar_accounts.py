"""
Check all Accounts Receivable accounts to find where the balance is coming from
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting import GeneralLedger, Account
from django.db.models import Sum, Q
from decimal import Decimal

print("=" * 80)
print("ALL ACCOUNTS RECEIVABLE ANALYSIS")
print("=" * 80)

# Find all AR accounts (1200-1299)
ar_accounts = Account.objects.filter(
    account_code__startswith='12',
    account_type='asset',
    is_deleted=False
).order_by('account_code')

print(f"\nFound {ar_accounts.count()} Accounts Receivable accounts (12xx):\n")

total_ar_balance = Decimal('0.00')

for account in ar_accounts:
    entries = GeneralLedger.objects.filter(
        account=account,
        is_deleted=False
    )
    
    debits = entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
    credits = entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
    
    # Asset balance = debits - credits
    balance = debits - credits
    
    if entries.exists() or balance != 0:
        print(f"{account.account_code} - {account.account_name}")
        print(f"  Entries: {entries.count()}")
        print(f"  Debits:  GHS {debits:,.2f}")
        print(f"  Credits: GHS {credits:,.2f}")
        print(f"  Balance: GHS {balance:,.2f}")
        
        if balance > 0:
            total_ar_balance += balance
        
        # Show recent entries if any
        if entries.exists():
            recent = entries.order_by('-transaction_date', '-created')[:3]
            print(f"  Recent entries:")
            for entry in recent:
                print(f"    - {entry.transaction_date}: DR {entry.debit_amount:,.2f} / CR {entry.credit_amount:,.2f} "
                      f"(Ref: {entry.reference_number or 'N/A'})")
        print()

print(f"{'='*80}")
print(f"TOTAL AR BALANCE: GHS {total_ar_balance:,.2f}")
print(f"{'='*80}")

# Check if there are any accounts with the exact amount from trial balance
target_amount = Decimal('1836602.62')
print(f"\n\nSearching for accounts with balance matching trial balance amount: GHS {target_amount:,.2f}")
print("-" * 80)

for account in ar_accounts:
    entries = GeneralLedger.objects.filter(
        account=account,
        is_deleted=False
    )
    
    debits = entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
    credits = entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
    balance = debits - credits
    
    if abs(balance - target_amount) < Decimal('0.01'):
        print(f"\n[FOUND] {account.account_code} - {account.account_name}")
        print(f"  Balance: GHS {balance:,.2f} (matches target!)")
        print(f"  Entries: {entries.count()}")
        
        # Show all entries
        print(f"  All entries:")
        for entry in entries.order_by('transaction_date', 'created'):
            print(f"    - {entry.transaction_date}: DR {entry.debit_amount:,.2f} / CR {entry.credit_amount:,.2f} "
                  f"(Ref: {entry.reference_number or 'N/A'}, Entry: {entry.entry_number})")

# Also check for accounts with similar large balances
print(f"\n\nAccounts with large balances (> GHS 1,000,000):")
print("-" * 80)

large_balances = []
for account in ar_accounts:
    entries = GeneralLedger.objects.filter(
        account=account,
        is_deleted=False
    )
    
    debits = entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
    credits = entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
    balance = debits - credits
    
    if balance > Decimal('1000000'):
        large_balances.append((account, balance, entries.count()))

if large_balances:
    for account, balance, count in sorted(large_balances, key=lambda x: x[1], reverse=True):
        print(f"  {account.account_code} - {account.account_name}: GHS {balance:,.2f} ({count} entries)")
else:
    print("  No accounts with balance > GHS 1,000,000")
