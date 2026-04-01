"""
Remove duplicate "Total" entry from Insurance Receivables
Keep only individual company entries
Ensure no duplicates in GL and Trial Balance
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting import Account
from django.db import transaction
from decimal import Decimal

# Try to import AdvancedGeneralLedger
try:
    from hospital.models_accounting_advanced import AdvancedGeneralLedger
    HAS_ADVANCED = True
except ImportError:
    HAS_ADVANCED = False

print("=" * 80)
print("REMOVE DUPLICATE TOTAL ENTRY")
print("Fix Insurance Receivables (1201)")
print("=" * 80)

# Get account 1201
acc_1201 = Account.objects.filter(account_code='1201', is_deleted=False).first()
if not acc_1201:
    print("  [ERROR] Account 1201 not found!")
    exit(1)

print(f"\n1. Checking account 1201 entries...")
print("-" * 80)

if HAS_ADVANCED:
    entries = AdvancedGeneralLedger.objects.filter(
        account=acc_1201,
        is_voided=False,
        is_deleted=False
    ).order_by('transaction_date', 'created', 'id')
    
    print(f"  Total entries: {entries.count()}")
    
    # Find the duplicate "Total" entry
    total_entry = None
    individual_entries = []
    total_of_individuals = Decimal('0.00')
    
    for entry in entries:
        desc_lower = entry.description.lower()
        if 'total' in desc_lower and len(individual_entries) > 0:
            # This is likely the duplicate total entry
            total_entry = entry
            print(f"\n  [FOUND] Duplicate Total entry:")
            print(f"    ID: {entry.id}")
            print(f"    Date: {entry.transaction_date}")
            print(f"    Amount: GHS {entry.debit_amount:,.2f}")
            print(f"    Description: {entry.description}")
        else:
            individual_entries.append(entry)
            total_of_individuals += entry.debit_amount
    
    print(f"\n  Individual entries: {len(individual_entries)}")
    print(f"  Sum of individual entries: GHS {total_of_individuals:,.2f}")
    
    if total_entry:
        print(f"  Duplicate Total entry amount: GHS {total_entry.debit_amount:,.2f}")
        print(f"  Difference: GHS {abs(total_of_individuals - total_entry.debit_amount):,.2f}")
        
        # Remove the duplicate total entry
        print(f"\n2. Removing duplicate Total entry...")
        print("-" * 80)
        
        with transaction.atomic():
            total_entry.is_voided = True
            total_entry.is_deleted = True
            total_entry.save()
            print(f"  [OK] Removed duplicate Total entry")
        
        # Recalculate balance
        remaining_entries = AdvancedGeneralLedger.objects.filter(
            account=acc_1201,
            is_voided=False,
            is_deleted=False
        )
        remaining_debits = sum(e.debit_amount for e in remaining_entries)
        remaining_credits = sum(e.credit_amount for e in remaining_entries)
        new_balance = remaining_debits - remaining_credits
        
        print(f"\n3. New balance after removal...")
        print("-" * 80)
        print(f"  Remaining entries: {remaining_entries.count()}")
        print(f"  Total Debits: GHS {remaining_debits:,.2f}")
        print(f"  Total Credits: GHS {remaining_credits:,.2f}")
        print(f"  New Balance: GHS {new_balance:,.2f}")
        
        # Check if this matches target
        target = Decimal('600834.40')
        if abs(new_balance - target) < Decimal('10000'):
            print(f"\n  [OK] Balance ({new_balance:,.2f}) is close to target ({target:,.2f})")
        else:
            print(f"\n  [NOTE] Balance ({new_balance:,.2f}) differs from target ({target:,.2f})")
            print(f"  Difference: GHS {abs(new_balance - target):,.2f}")
    else:
        print(f"\n  [OK] No duplicate Total entry found")
        print(f"  Current balance: GHS {total_of_individuals:,.2f}")

# Check for other duplicates
print(f"\n4. Checking for other duplicates...")
print("-" * 80)

if HAS_ADVANCED:
    entries = AdvancedGeneralLedger.objects.filter(
        account=acc_1201,
        is_voided=False,
        is_deleted=False
    ).order_by('transaction_date', 'created', 'id')
    
    seen = {}
    duplicates = []
    
    for entry in entries:
        # Key: date, description, debit, credit
        key = (
            entry.transaction_date,
            entry.description[:50],  # First 50 chars of description
            entry.debit_amount,
            entry.credit_amount
        )
        
        if key in seen:
            duplicates.append((seen[key], entry))
        else:
            seen[key] = entry
    
    if duplicates:
        print(f"  [WARNING] Found {len(duplicates)} duplicate pairs:")
        for dup1, dup2 in duplicates:
            print(f"    - Entry 1: {dup1.id} - {dup1.description[:40]}")
            print(f"      Entry 2: {dup2.id} - {dup2.description[:40]}")
    else:
        print(f"  [OK] No other duplicates found")

print("\n" + "=" * 80)
print("DUPLICATE REMOVAL COMPLETE")
print("=" * 80)
