"""
Check ALL revenue entries including deleted ones and check for issues
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
print("COMPREHENSIVE REVENUE ENTRIES CHECK")
print("=" * 80)

# Check ALL entries (including deleted)
print("\n1. Checking ALL entries (including deleted):")
print("-" * 80)

revenue_accounts = Account.objects.filter(account_type='revenue', is_deleted=False).order_by('account_code')

for account in revenue_accounts:
    all_entries = GeneralLedger.objects.filter(account=account)
    active_entries = GeneralLedger.objects.filter(account=account, is_deleted=False)
    
    all_debits = all_entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
    all_credits = all_entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
    
    active_debits = active_entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
    active_credits = active_entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
    
    deleted_count = all_entries.filter(is_deleted=True).count()
    
    print(f"\n{account.account_code} - {account.account_name}:")
    print(f"  Active entries: {active_entries.count()}")
    print(f"  Deleted entries: {deleted_count}")
    print(f"  Active Credits: GHS {active_credits:,.2f}")
    print(f"  All Credits (including deleted): GHS {all_credits:,.2f}")
    
    if deleted_count > 0:
        print(f"  [WARNING] Has {deleted_count} deleted entries that might affect totals")

# Check for entries with very large amounts
print("\n\n2. Checking for entries with unusual amounts:")
print("-" * 80)

large_entries = GeneralLedger.objects.filter(
    account__account_type='revenue',
    credit_amount__gt=1000,
    is_deleted=False
).order_by('-credit_amount')

if large_entries.exists():
    print(f"[WARNING] Found {large_entries.count()} revenue entries with amount > GHS 1,000:")
    for entry in large_entries[:10]:
        print(f"  {entry.account.account_code} - {entry.account.account_name}: "
              f"GHS {entry.credit_amount:,.2f} on {entry.transaction_date} "
              f"(Ref: {entry.reference_number or 'N/A'}, Entry: {entry.entry_number})")
else:
    print("[OK] No unusually large entries found")

# Check for entries with same reference appearing multiple times
print("\n\n3. Checking for duplicate reference numbers in revenue accounts:")
print("-" * 80)

from collections import defaultdict
ref_account_map = defaultdict(lambda: defaultdict(list))

revenue_entries = GeneralLedger.objects.filter(
    account__account_type='revenue',
    is_deleted=False,
    reference_number__isnull=False
).exclude(reference_number='')

for entry in revenue_entries:
    ref_account_map[entry.reference_number][entry.account.account_code].append(entry)

duplicates = {ref: accounts for ref, accounts in ref_account_map.items() 
             if any(len(entries) > 1 for entries in accounts.values())}

if duplicates:
    print(f"[WARNING] Found {len(duplicates)} reference numbers with multiple entries:")
    for ref_num, accounts in list(duplicates.items())[:10]:
        print(f"\n  Reference: {ref_num}")
        for acc_code, entries in accounts.items():
            if len(entries) > 1:
                total = sum(e.credit_amount for e in entries)
                print(f"    Account {acc_code}: {len(entries)} entries, Total: GHS {total:,.2f}")
                for entry in entries:
                    print(f"      - Entry {entry.entry_number}: GHS {entry.credit_amount:,.2f} on {entry.transaction_date}")
else:
    print("[OK] No duplicate reference numbers found")

# Check what the trial balance view would calculate
print("\n\n4. Simulating Trial Balance Calculation (as of today):")
print("-" * 80)

from django.utils import timezone
report_date = timezone.now().date()

print(f"Report Date: {report_date}")

total_trial_debits = Decimal('0.00')
total_trial_credits = Decimal('0.00')

for account in revenue_accounts:
    entries = GeneralLedger.objects.filter(
        account=account,
        transaction_date__lte=report_date,
        is_deleted=False
    )
    
    debits = entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
    credits = entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
    
    # Trial balance calculation (as per fixed view)
    balance = credits - debits
    
    if debits > 0 or credits > 0:
        print(f"\n{account.account_code} - {account.account_name}:")
        print(f"  Debits:  GHS {debits:,.2f}")
        print(f"  Credits: GHS {credits:,.2f}")
        print(f"  Balance: GHS {balance:,.2f} (should show in {'CREDIT' if balance >= 0 else 'DEBIT'} column)")
        
        total_trial_debits += debits
        total_trial_credits += credits

print(f"\n{'='*80}")
print(f"Trial Balance Totals:")
print(f"  Total Debits:  GHS {total_trial_debits:,.2f}")
print(f"  Total Credits: GHS {total_trial_credits:,.2f}")
print(f"{'='*80}")
