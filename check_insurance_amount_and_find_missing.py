"""
Check why insurance amount is 1.8M instead of 600K
Find missing entries or check if Accounts Payable is related
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting import Account, GeneralLedger
from django.db.models import Sum, Q
from decimal import Decimal

# Try to import AdvancedGeneralLedger
try:
    from hospital.models_accounting_advanced import AdvancedGeneralLedger
    HAS_ADVANCED = True
except ImportError:
    HAS_ADVANCED = False

print("=" * 80)
print("CHECKING INSURANCE AMOUNT DISCREPANCY")
print("Target: ~GHS 600,834.40")
print("Current: GHS 1,836,602.62")
print("=" * 80)

# Check account 1201
print("\n1. Checking account 1201 (Insurance Receivables)...")
print("-" * 80)

acc_1201 = Account.objects.filter(account_code='1201', is_deleted=False).first()
if acc_1201:
    if HAS_ADVANCED:
        entries = AdvancedGeneralLedger.objects.filter(
            account=acc_1201,
            is_voided=False,
            is_deleted=False
        )
        
        print(f"  Entries: {entries.count()}")
        print(f"\n  All entries:")
        total = Decimal('0.00')
        for entry in entries.order_by('transaction_date', 'created'):
            total += entry.debit_amount
            print(f"    - {entry.transaction_date}: DR {entry.debit_amount:,.2f} / CR {entry.credit_amount:,.2f}")
            print(f"      Desc: {entry.description[:60]}")
            print(f"      Total so far: GHS {total:,.2f}")
            if total >= Decimal('600000'):
                print(f"      [REACHED 600K MARK]")
        
        debits = entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
        credits = entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
        balance = debits - credits
        print(f"\n  Total Debits: GHS {debits:,.2f}")
        print(f"  Total Credits: GHS {credits:,.2f}")
        print(f"  Balance: GHS {balance:,.2f}")

# Check Accounts Payable (2000) - maybe it's related?
print("\n2. Checking Accounts Payable (2000)...")
print("-" * 80)

acc_2000 = Account.objects.filter(account_code='2000', is_deleted=False).first()
if acc_2000:
    if HAS_ADVANCED:
        entries = AdvancedGeneralLedger.objects.filter(
            account=acc_2000,
            is_voided=False,
            is_deleted=False
        )
        
        debits = entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
        credits = entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
        balance = credits - debits  # Liability
        
        print(f"  Entries: {entries.count()}")
        print(f"  Total Debits: GHS {debits:,.2f}")
        print(f"  Total Credits: GHS {credits:,.2f}")
        print(f"  Balance: GHS {balance:,.2f}")
        
        if entries.exists():
            print(f"\n  All entries:")
            for entry in entries:
                print(f"    - {entry.transaction_date}: DR {entry.debit_amount:,.2f} / CR {entry.credit_amount:,.2f}")
                print(f"      Desc: {entry.description[:60]}")

# Check if there are entries that sum to ~600K
print("\n3. Finding entries that sum to ~GHS 600,834.40...")
print("-" * 80)

target_amount = Decimal('600834.40')
if HAS_ADVANCED and acc_1201:
    entries = AdvancedGeneralLedger.objects.filter(
        account=acc_1201,
        is_voided=False,
        is_deleted=False
    ).order_by('transaction_date', 'created')
    
    # Try to find a subset that sums to target
    running_total = Decimal('0.00')
    matching_entries = []
    
    for entry in entries:
        running_total += entry.debit_amount
        matching_entries.append(entry)
        
        if abs(running_total - target_amount) < Decimal('1.00'):
            print(f"  [FOUND MATCH] Entries sum to: GHS {running_total:,.2f}")
            print(f"    Number of entries: {len(matching_entries)}")
            break
        elif running_total > target_amount:
            print(f"  [EXCEEDED] Running total: GHS {running_total:,.2f} (exceeds target)")
            break
    
    # Check if some entries should be excluded
    print(f"\n  Checking if some entries should be excluded...")
    print(f"  Total entries: {entries.count()}")
    print(f"  If we need ~600K from 1.8M, that's about {600834.40 / 1836602.62 * 100:.1f}% of entries")

# Check for corporate accounts separately
print("\n4. Checking for separate corporate accounts...")
print("-" * 80)

corporate_accounts = Account.objects.filter(
    Q(account_name__icontains='corporate') |
    Q(account_code__startswith='12')
).filter(is_deleted=False).exclude(account_code='1201')

print(f"  Found {corporate_accounts.count()} other accounts:")
for acc in corporate_accounts:
    if HAS_ADVANCED:
        entries = AdvancedGeneralLedger.objects.filter(
            account=acc,
            is_voided=False,
            is_deleted=False
        )
        debits = entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
        credits = entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
        if acc.account_type in ['asset', 'expense']:
            balance = debits - credits
        else:
            balance = credits - debits
        print(f"    - {acc.account_code}: {acc.account_name}")
        print(f"      Entries: {entries.count()}, Balance: GHS {balance:,.2f}")

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
