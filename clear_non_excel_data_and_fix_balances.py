"""
Clear all non-Excel imported data and fix General Ledger balance calculations
Only keeps data imported from Excel (Jerry import, Insurance adjudication)
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
from django.db.models import Sum
from decimal import Decimal

print("=" * 80)
print("CLEARING NON-EXCEL DATA AND FIXING BALANCES")
print("=" * 80)

# Identify Excel-imported entries (from Jerry import or Insurance adjudication)
# These typically have specific reference patterns
excel_reference_patterns = [
    'JERRY', 'jerry', 'EXCEL', 'excel', 'IMPORT', 'import',
    'INSURANCE', 'insurance', 'ADJUDICATION', 'adjudication'
]

print("\n1. Identifying Excel-imported entries...")
print("-" * 80)

# Get all GeneralLedger entries
all_gl_entries = GeneralLedger.objects.filter(is_deleted=False)

# Find Excel-imported entries
excel_entries = []
non_excel_entries = []

for entry in all_gl_entries:
    is_excel = False
    
    # Check reference_number
    if entry.reference_number:
        for pattern in excel_reference_patterns:
            if pattern in entry.reference_number.upper():
                is_excel = True
                break
    
    # Check description
    if not is_excel and entry.description:
        for pattern in excel_reference_patterns:
            if pattern in entry.description.upper():
                is_excel = True
                break
    
    # Check reference_type
    if not is_excel and entry.reference_type:
        if 'import' in entry.reference_type.lower() or 'excel' in entry.reference_type.lower():
            is_excel = True
    
    if is_excel:
        excel_entries.append(entry)
    else:
        non_excel_entries.append(entry)

print(f"  Excel-imported entries: {len(excel_entries)}")
print(f"  Non-Excel entries to remove: {len(non_excel_entries)}")

# Show summary of what will be deleted
if non_excel_entries:
    total_debits = sum(e.debit_amount for e in non_excel_entries)
    total_credits = sum(e.credit_amount for e in non_excel_entries)
    print(f"\n  Non-Excel entries summary:")
    print(f"    Total Debits: GHS {total_debits:,.2f}")
    print(f"    Total Credits: GHS {total_credits:,.2f}")

# Clear non-Excel entries
print("\n2. Clearing non-Excel entries...")
print("-" * 80)

with transaction.atomic():
    deleted_count = 0
    for entry in non_excel_entries:
        entry.is_deleted = True
        entry.save()
        deleted_count += 1
    
    print(f"  [OK] Marked {deleted_count} non-Excel entries as deleted")

# Clear all revenue entries (as requested)
print("\n3. Clearing all revenue entries...")
print("-" * 80)

revenue_accounts = Account.objects.filter(account_type='revenue', is_deleted=False)
revenue_entries = GeneralLedger.objects.filter(
    account__account_type='revenue',
    is_deleted=False
)

revenue_count = revenue_entries.count()
revenue_debits = revenue_entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
revenue_credits = revenue_entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')

print(f"  Found {revenue_count} revenue entries")
print(f"  Total Debits: GHS {revenue_debits:,.2f}")
print(f"  Total Credits: GHS {revenue_credits:,.2f}")

with transaction.atomic():
    for entry in revenue_entries:
        entry.is_deleted = True
        entry.save()
    
    print(f"  [OK] Marked {revenue_count} revenue entries as deleted")

# Fix General Ledger balance calculations
print("\n4. Fixing General Ledger balance calculations...")
print("-" * 80)

# Get all active accounts
accounts = Account.objects.filter(is_deleted=False)

fixed_count = 0
for account in accounts:
    # Get all entries for this account (including deleted for calculation)
    entries = GeneralLedger.objects.filter(
        account=account
    ).order_by('transaction_date', 'created', 'id')
    
    if not entries.exists():
        continue
    
    # Calculate running balance correctly based on account type
    running_balance = Decimal('0.00')
    
    for entry in entries:
        if entry.is_deleted:
            continue  # Skip deleted entries for balance calculation
        
        # Calculate balance change
        if account.account_type in ['asset', 'expense']:
            # Assets and Expenses: Debit increases, Credit decreases
            balance_change = entry.debit_amount - entry.credit_amount
        else:
            # Liabilities, Equity, Revenue: Credit increases, Debit decreases
            balance_change = entry.credit_amount - entry.debit_amount
        
        # Update running balance
        running_balance += balance_change
        
        # Update entry balance if different
        if entry.balance != running_balance:
            entry.balance = running_balance
            entry.save(update_fields=['balance'])
            fixed_count += 1

print(f"  [OK] Fixed {fixed_count} balance calculations")

# Verify balances
print("\n5. Verifying balances...")
print("-" * 80)

for account in accounts:
    entries = GeneralLedger.objects.filter(account=account, is_deleted=False)
    
    if entries.exists():
        debits = entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
        credits = entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
        
        if account.account_type in ['asset', 'expense']:
            expected_balance = debits - credits
        else:
            expected_balance = credits - debits
        
        # Get last entry balance
        last_entry = entries.order_by('transaction_date', 'created', 'id').last()
        actual_balance = last_entry.balance if last_entry else Decimal('0.00')
        
        if abs(expected_balance - actual_balance) > Decimal('0.01'):
            print(f"  [WARNING] {account.account_code} - {account.account_name}:")
            print(f"    Expected: GHS {expected_balance:,.2f}, Actual: GHS {actual_balance:,.2f}")

print("\n" + "=" * 80)
print("CLEANUP AND FIX COMPLETE")
print("=" * 80)
print(f"\nSummary:")
print(f"  - Non-Excel entries deleted: {len(non_excel_entries)}")
print(f"  - Revenue entries deleted: {revenue_count}")
print(f"  - Balance calculations fixed: {fixed_count}")
print(f"\n[OK] Data cleaned and balances fixed!")
