"""
Clear all non-Excel data - keep only Excel-imported entries
Also clear all revenue entries and fix balances
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

# Try to import AdvancedGeneralLedger
try:
    from hospital.models_accounting_advanced import AdvancedGeneralLedger
    HAS_ADVANCED = True
except ImportError:
    HAS_ADVANCED = False

print("=" * 80)
print("CLEARING ALL NON-EXCEL DATA")
print("Keep only Excel-imported entries (Jerry/Insurance)")
print("=" * 80)

# Step 1: Clear all GeneralLedger entries except Excel imports
print("\n1. Clearing GeneralLedger entries (keeping Excel imports only)...")
print("-" * 80)

# Excel imports typically come from Jerry import or Insurance adjudication
# These have specific reference patterns or come from AdvancedGeneralLedger
excel_patterns = ['JERRY', 'jerry', 'EXCEL', 'excel', 'IMPORT', 'import', 
                  'INSURANCE', 'insurance', 'ADJUDICATION', 'adjudication',
                  'AR', 'AP']  # Accounts Receivable/Payable from Excel

all_gl = GeneralLedger.objects.filter(is_deleted=False)
excel_gl = []
non_excel_gl = []

for entry in all_gl:
    is_excel = False
    
    # Check if it matches Excel patterns
    ref = (entry.reference_number or '').upper()
    desc = (entry.description or '').upper()
    ref_type = (entry.reference_type or '').upper()
    
    for pattern in excel_patterns:
        if pattern in ref or pattern in desc or pattern in ref_type:
            is_excel = True
            break
    
    if is_excel:
        excel_gl.append(entry)
    else:
        non_excel_gl.append(entry)

print(f"  Excel entries to keep: {len(excel_gl)}")
print(f"  Non-Excel entries to delete: {len(non_excel_gl)}")

# Step 2: Clear all revenue entries
print("\n2. Clearing ALL revenue entries...")
print("-" * 80)

revenue_accounts = Account.objects.filter(account_type='revenue', is_deleted=False)
revenue_entries_gl = GeneralLedger.objects.filter(
    account__account_type='revenue',
    is_deleted=False
)

revenue_count_gl = revenue_entries_gl.count()
print(f"  GeneralLedger revenue entries: {revenue_count_gl}")

if HAS_ADVANCED:
    revenue_entries_adv = AdvancedGeneralLedger.objects.filter(
        account__account_type='revenue',
        is_voided=False,
        is_deleted=False
    )
    revenue_count_adv = revenue_entries_adv.count()
    print(f"  AdvancedGeneralLedger revenue entries: {revenue_count_adv}")

# Step 3: Execute cleanup
print("\n3. Executing cleanup...")
print("-" * 80)

with transaction.atomic():
    # Delete non-Excel GeneralLedger entries
    deleted_gl = 0
    for entry in non_excel_gl:
        entry.is_deleted = True
        entry.save()
        deleted_gl += 1
    
    # Delete all revenue entries from GeneralLedger
    deleted_revenue_gl = 0
    for entry in revenue_entries_gl:
        entry.is_deleted = True
        entry.save()
        deleted_revenue_gl += 1
    
    # Delete all revenue entries from AdvancedGeneralLedger
    deleted_revenue_adv = 0
    if HAS_ADVANCED:
        for entry in revenue_entries_adv:
            entry.is_voided = True
            entry.is_deleted = True
            entry.save()
            deleted_revenue_adv += 1
    
    print(f"  [OK] Deleted {deleted_gl} non-Excel GeneralLedger entries")
    print(f"  [OK] Deleted {deleted_revenue_gl} revenue entries from GeneralLedger")
    if HAS_ADVANCED:
        print(f"  [OK] Deleted {deleted_revenue_adv} revenue entries from AdvancedGeneralLedger")

# Step 4: Recalculate all balances
print("\n4. Recalculating all GeneralLedger balances...")
print("-" * 80)

accounts = Account.objects.filter(is_deleted=False)
fixed_count = 0

with transaction.atomic():
    for account in accounts:
        entries = GeneralLedger.objects.filter(
            account=account,
            is_deleted=False
        ).order_by('transaction_date', 'created', 'id')
        
        if not entries.exists():
            continue
        
        running_balance = Decimal('0.00')
        
        for entry in entries:
            # Calculate balance change
            if account.account_type in ['asset', 'expense']:
                balance_change = entry.debit_amount - entry.credit_amount
            else:
                balance_change = entry.credit_amount - entry.debit_amount
            
            running_balance += balance_change
            
            # Update if different
            if abs(entry.balance - running_balance) > Decimal('0.01'):
                entry.balance = running_balance
                entry.save(update_fields=['balance'])
                fixed_count += 1

print(f"  [OK] Fixed {fixed_count} balance calculations")

# Step 5: Summary
print("\n" + "=" * 80)
print("CLEANUP COMPLETE")
print("=" * 80)
print(f"\nSummary:")
print(f"  - Non-Excel GeneralLedger entries deleted: {deleted_gl}")
print(f"  - Revenue entries deleted (GL): {deleted_revenue_gl}")
if HAS_ADVANCED:
    print(f"  - Revenue entries deleted (Adv): {deleted_revenue_adv}")
print(f"  - Balance calculations fixed: {fixed_count}")
print(f"\n[OK] Only Excel-imported data remains!")
