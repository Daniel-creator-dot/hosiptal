"""
Verify Balance Display - Check Each Entry's Balance Matches Debit
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting_advanced import AdvancedGeneralLedger
from django.utils import timezone
from decimal import Decimal
from datetime import datetime

print("=" * 80)
print("VERIFYING BALANCE DISPLAY - INDEPENDENT BALANCES")
print("=" * 80)

# Check entries for Jan 7, 2026
check_date = datetime(2026, 1, 7).date()
print(f"\nChecking entries for: {check_date.strftime('%B %d, %Y')}")

# Get all entries
ledger_entries = AdvancedGeneralLedger.objects.filter(
    transaction_date=check_date,
    is_voided=False
).select_related('account').order_by('account', 'transaction_date')

print(f"\nTotal entries: {ledger_entries.count()}")

# Verify each entry's balance matches its debit amount
print(f"\n" + "=" * 80)
print("VERIFYING BALANCE = DEBIT AMOUNT (Independent Balances):")
print("=" * 80)

errors = []
correct = 0

for entry in ledger_entries:
    # Expected balance (should match debit amount for Excel entries)
    expected_balance = entry.debit_amount if entry.debit_amount > 0 else entry.credit_amount
    
    # Actual balance from database
    actual_balance = entry.balance
    
    # Check if they match
    if abs(expected_balance - actual_balance) < 0.01:
        correct += 1
        status = "[OK]"
    else:
        errors.append({
            'entry': entry,
            'expected': expected_balance,
            'actual': actual_balance,
            'debit': entry.debit_amount,
            'credit': entry.credit_amount
        })
        status = "[ERROR]"
    
    print(f"{status} {entry.account.account_code} - {entry.description[:50]}")
    print(f"    Debit: GHS {entry.debit_amount:,.2f} | Credit: GHS {entry.credit_amount:,.2f}")
    print(f"    Expected Balance: GHS {expected_balance:,.2f} | Actual Balance: GHS {actual_balance:,.2f}")

print(f"\n" + "=" * 80)
print("SUMMARY:")
print("=" * 80)
print(f"  Total Entries: {ledger_entries.count()}")
print(f"  Correct (Balance = Debit): {correct}")
print(f"  Errors (Balance != Debit): {len(errors)}")

if errors:
    print(f"\n  ERRORS FOUND:")
    for error in errors:
        print(f"    - {error['entry'].description[:50]}")
        print(f"      Expected: GHS {error['expected']:,.2f}, Actual: GHS {error['actual']:,.2f}")
        print(f"      Debit: GHS {error['debit']:,.2f}, Credit: GHS {error['credit']:,.2f}")

# Check what the view would display
print(f"\n" + "=" * 80)
print("WHAT VIEW WILL DISPLAY:")
print("=" * 80)

for entry in ledger_entries[:10]:  # Show first 10
    # Simulate view logic
    if entry.debit_amount and entry.debit_amount > 0:
        display_balance = entry.debit_amount
    elif entry.credit_amount and entry.credit_amount > 0:
        display_balance = entry.credit_amount
    elif entry.balance and entry.balance != 0:
        display_balance = entry.balance
    else:
        display_balance = Decimal('0.00')
    
    print(f"  {entry.description[:50]}")
    print(f"    Debit: GHS {entry.debit_amount:,.2f}")
    print(f"    Display Balance: GHS {display_balance:,.2f}")
    print(f"    Match: {'[OK]' if abs(display_balance - entry.debit_amount) < 0.01 else '[CHECK]'}")

print("\n" + "=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)
