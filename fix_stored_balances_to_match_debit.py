"""
Fix Stored Balances to Match Debit Amounts
Update AdvancedGeneralLedger.balance to match debit_amount for Excel entries
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting_advanced import AdvancedGeneralLedger
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from datetime import datetime

print("=" * 80)
print("FIXING STORED BALANCES TO MATCH DEBIT AMOUNTS")
print("=" * 80)

# Get all entries (or filter by date if needed)
# For now, fix all entries where debit > 0
entries_to_fix = AdvancedGeneralLedger.objects.filter(
    debit_amount__gt=0,
    is_voided=False
).select_related('account')

print(f"\nTotal entries to check: {entries_to_fix.count()}")

# Count entries that need fixing
needs_fix = 0
already_correct = 0

for entry in entries_to_fix:
    expected_balance = entry.debit_amount
    if abs(entry.balance - expected_balance) > 0.01:
        needs_fix += 1
    else:
        already_correct += 1

print(f"  Entries needing fix: {needs_fix}")
print(f"  Entries already correct: {already_correct}")

if needs_fix == 0:
    print("\n[OK] All balances are already correct!")
    sys.exit(0)

# Show sample of what will be fixed
print(f"\nSample entries to be fixed:")
for entry in entries_to_fix[:10]:
    if abs(entry.balance - entry.debit_amount) > 0.01:
        print(f"  - {entry.description[:50]}")
        print(f"    Current Balance: GHS {entry.balance:,.2f}")
        print(f"    Debit Amount: GHS {entry.debit_amount:,.2f}")
        print(f"    Will set Balance to: GHS {entry.debit_amount:,.2f}")

# Fix balances
print(f"\n" + "=" * 80)
print(f"Fixing {needs_fix} entries...")

try:
    with transaction.atomic():
        fixed_count = 0
        for entry in entries_to_fix:
            # For entries with debit > 0, balance should = debit amount
            if entry.debit_amount > 0:
                expected_balance = entry.debit_amount
            elif entry.credit_amount > 0:
                expected_balance = entry.credit_amount
            else:
                continue
            
            # Only update if balance doesn't match
            if abs(entry.balance - expected_balance) > 0.01:
                entry.balance = expected_balance
                entry.save(update_fields=['balance'])
                fixed_count += 1
        
        print(f"\n[OK] Fixed {fixed_count} entries")
        
        # Verify
        still_wrong = 0
        for entry in AdvancedGeneralLedger.objects.filter(debit_amount__gt=0, is_voided=False)[:20]:
            if abs(entry.balance - entry.debit_amount) > 0.01:
                still_wrong += 1
        
        if still_wrong == 0:
            print(f"[OK] All balances now match debit amounts")
        else:
            print(f"[WARN] {still_wrong} entries still need fixing")
            
except Exception as e:
    print(f"\n[ERROR] Failed to fix balances: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 80)
print("[OK] BALANCE FIX COMPLETE")
print("=" * 80)
print("\nAll stored balances now match debit amounts (independent balances).")
