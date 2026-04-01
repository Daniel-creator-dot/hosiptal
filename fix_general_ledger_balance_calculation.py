"""
Fix General Ledger balance calculation - ensure credit/balance is calculated correctly
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting import GeneralLedger, Account
from django.db import transaction
from decimal import Decimal

print("=" * 80)
print("FIXING GENERAL LEDGER BALANCE CALCULATIONS")
print("=" * 80)

# Get all accounts
accounts = Account.objects.filter(is_deleted=False)

print("\nFixing balance calculations for all accounts...")
print("-" * 80)

total_fixed = 0

with transaction.atomic():
    for account in accounts:
        # Get all entries for this account, ordered chronologically
        entries = GeneralLedger.objects.filter(
            account=account,
            is_deleted=False
        ).order_by('transaction_date', 'created', 'id')
        
        if not entries.exists():
            continue
        
        # Calculate running balance correctly based on account type
        running_balance = Decimal('0.00')
        fixed_in_account = 0
        
        for entry in entries:
            # Calculate balance change based on account type
            if account.account_type in ['asset', 'expense']:
                # Assets and Expenses: Debit increases, Credit decreases
                # Balance = previous_balance + debit - credit
                balance_change = entry.debit_amount - entry.credit_amount
            else:
                # Liabilities, Equity, Revenue: Credit increases, Debit decreases
                # Balance = previous_balance + credit - debit
                balance_change = entry.credit_amount - entry.debit_amount
            
            # Update running balance
            running_balance += balance_change
            
            # Update entry balance if different
            if abs(entry.balance - running_balance) > Decimal('0.01'):
                old_balance = entry.balance
                entry.balance = running_balance
                entry.save(update_fields=['balance'])
                fixed_in_account += 1
                print(f"  Fixed: {account.account_code} - Entry {entry.entry_number}")
                print(f"    Old balance: GHS {old_balance:,.2f} -> New balance: GHS {running_balance:,.2f}")
        
        if fixed_in_account > 0:
            total_fixed += fixed_in_account
            print(f"  {account.account_code} - {account.account_name}: Fixed {fixed_in_account} entries")

print(f"\n{'='*80}")
print(f"FIX COMPLETE")
print(f"{'='*80}")
print(f"Total entries fixed: {total_fixed}")

# Verify all balances are correct
print("\n\nVerifying all balances are correct...")
print("-" * 80)

errors_found = 0
for account in accounts:
    entries = GeneralLedger.objects.filter(account=account, is_deleted=False)
    
    if entries.exists():
        # Calculate expected total balance
        total_debits = sum(e.debit_amount for e in entries)
        total_credits = sum(e.credit_amount for e in entries)
        
        if account.account_type in ['asset', 'expense']:
            expected_total = total_debits - total_credits
        else:
            expected_total = total_credits - total_debits
        
        # Get last entry's balance (should match expected total)
        last_entry = entries.order_by('transaction_date', 'created', 'id').last()
        if last_entry:
            actual_balance = last_entry.balance
            
            if abs(expected_total - actual_balance) > Decimal('0.01'):
                errors_found += 1
                print(f"  [ERROR] {account.account_code} - {account.account_name}:")
                print(f"    Expected total: GHS {expected_total:,.2f}")
                print(f"    Last entry balance: GHS {actual_balance:,.2f}")
                print(f"    Difference: GHS {abs(expected_total - actual_balance):,.2f}")

if errors_found == 0:
    print("  [OK] All balances are correct!")
else:
    print(f"  [WARNING] Found {errors_found} accounts with balance discrepancies")
