"""
Check Insurance Receivables account for errors and duplicates
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting import GeneralLedger, Account
from django.db.models import Sum, Q, Count
from decimal import Decimal
from collections import defaultdict

print("=" * 80)
print("INSURANCE RECEIVABLES ANALYSIS")
print("=" * 80)

# Find Insurance Receivables account
insurance_ar_accounts = Account.objects.filter(
    Q(account_code='1201') | 
    Q(account_name__icontains='Insurance Receivable') |
    Q(account_name__icontains='Insurance Receivables'),
    is_deleted=False
).order_by('account_code')

if not insurance_ar_accounts.exists():
    print("\n[WARNING] No Insurance Receivables account found!")
    print("Searching for similar accounts...")
    ar_accounts = Account.objects.filter(
        account_type='asset',
        account_code__startswith='12',
        is_deleted=False
    )
    print(f"\nFound {ar_accounts.count()} asset accounts starting with 12:")
    for acc in ar_accounts:
        print(f"  {acc.account_code} - {acc.account_name}")

for account in insurance_ar_accounts:
    print(f"\n{'='*80}")
    print(f"Account: {account.account_code} - {account.account_name}")
    print(f"{'='*80}")
    
    # Get all entries
    all_entries = GeneralLedger.objects.filter(account=account)
    active_entries = GeneralLedger.objects.filter(account=account, is_deleted=False)
    
    # Calculate totals
    all_debits = all_entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
    all_credits = all_entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
    
    active_debits = active_entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
    active_credits = active_entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
    
    # Asset balance = debits - credits
    all_balance = all_debits - all_credits
    active_balance = active_debits - active_credits
    
    deleted_count = all_entries.filter(is_deleted=True).count()
    
    print(f"\nSummary:")
    print(f"  Active entries: {active_entries.count()}")
    print(f"  Deleted entries: {deleted_count}")
    print(f"  Active Debits:  GHS {active_debits:,.2f}")
    print(f"  Active Credits: GHS {active_credits:,.2f}")
    print(f"  Active Balance: GHS {active_balance:,.2f} (should be positive for asset)")
    
    if deleted_count > 0:
        print(f"\n[WARNING] Has {deleted_count} deleted entries")
        print(f"  All Debits:  GHS {all_debits:,.2f}")
        print(f"  All Credits: GHS {all_credits:,.2f}")
        print(f"  All Balance: GHS {all_balance:,.2f}")
    
    # Check for duplicate entries
    print(f"\n\n1. Checking for duplicate entries...")
    print("-" * 80)
    
    # Group by reference number
    ref_groups = defaultdict(list)
    for entry in active_entries:
        if entry.reference_number:
            ref_groups[entry.reference_number].append(entry)
    
    duplicate_refs = {ref: entries for ref, entries in ref_groups.items() if len(entries) > 1}
    
    if duplicate_refs:
        print(f"[WARNING] Found {len(duplicate_refs)} reference numbers with multiple entries:")
        total_dup_amount = Decimal('0.00')
        for ref_num, entries in list(duplicate_refs.items())[:20]:
            total_dup_debits = sum(e.debit_amount for e in entries)
            total_dup_credits = sum(e.credit_amount for e in entries)
            dup_amount = total_dup_debits - total_dup_credits
            print(f"\n  Reference: {ref_num}")
            print(f"  Duplicate count: {len(entries)}")
            print(f"  Total Debits: GHS {total_dup_debits:,.2f}")
            print(f"  Total Credits: GHS {total_dup_credits:,.2f}")
            print(f"  Net Amount: GHS {dup_amount:,.2f}")
            for i, entry in enumerate(entries, 1):
                print(f"    {i}. Entry {entry.entry_number}: DR {entry.debit_amount:,.2f} / CR {entry.credit_amount:,.2f} "
                      f"on {entry.transaction_date} (ID: {entry.pk}, Created: {entry.created})")
            total_dup_amount += dup_amount * (len(entries) - 1)
        print(f"\n  Estimated duplicate amount: GHS {total_dup_amount:,.2f}")
    else:
        print("[OK] No duplicates found by reference number")
    
    # Check for entries with same amount and date
    print(f"\n\n2. Checking for entries with same amount and date...")
    print("-" * 80)
    
    amount_date_groups = defaultdict(list)
    for entry in active_entries:
        key = (entry.debit_amount, entry.credit_amount, entry.transaction_date)
        amount_date_groups[key].append(entry)
    
    duplicate_groups = {key: entries for key, entries in amount_date_groups.items() 
                        if len(entries) > 1}
    
    if duplicate_groups:
        print(f"[WARNING] Found {len(duplicate_groups)} groups of duplicate entries (same amount & date):")
        for (debit, credit, date), entries in list(duplicate_groups.items())[:10]:
            print(f"\n  Amount: DR {debit:,.2f} / CR {credit:,.2f}, Date: {date}")
            print(f"  Duplicate count: {len(entries)}")
            for i, entry in enumerate(entries, 1):
                print(f"    {i}. Entry {entry.entry_number}: Ref {entry.reference_number or 'N/A'} "
                      f"(ID: {entry.pk}, Created: {entry.created})")
    else:
        print("[OK] No duplicates found by amount/date")
    
    # Check for entries without reference numbers
    print(f"\n\n3. Checking for entries without reference numbers...")
    print("-" * 80)
    
    entries_no_ref = active_entries.filter(Q(reference_number='') | Q(reference_number__isnull=True))
    
    if entries_no_ref.exists():
        no_ref_debits = entries_no_ref.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
        no_ref_credits = entries_no_ref.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
        print(f"[WARNING] Found {entries_no_ref.count()} entries without reference numbers:")
        print(f"  Total Debits: GHS {no_ref_debits:,.2f}")
        print(f"  Total Credits: GHS {no_ref_credits:,.2f}")
        print(f"  Net Amount: GHS {no_ref_debits - no_ref_credits:,.2f}")
        for entry in entries_no_ref[:10]:
            print(f"    - Entry {entry.entry_number}: DR {entry.debit_amount:,.2f} / CR {entry.credit_amount:,.2f} "
                  f"on {entry.transaction_date} (ID: {entry.pk})")
    else:
        print("[OK] All entries have reference numbers")
    
    # Check for unusually large entries
    print(f"\n\n4. Checking for unusually large entries...")
    print("-" * 80)
    
    large_entries = active_entries.filter(debit_amount__gt=100000).order_by('-debit_amount')
    
    if large_entries.exists():
        print(f"[WARNING] Found {large_entries.count()} entries with debit amount > GHS 100,000:")
        for entry in large_entries[:10]:
            print(f"  Entry {entry.entry_number}: DR {entry.debit_amount:,.2f} / CR {entry.credit_amount:,.2f} "
                  f"on {entry.transaction_date} (Ref: {entry.reference_number or 'N/A'})")
    else:
        print("[OK] No unusually large entries found")
    
    # Show recent entries
    print(f"\n\n5. Recent Entries (last 10):")
    print("-" * 80)
    
    recent_entries = active_entries.order_by('-transaction_date', '-created')[:10]
    if recent_entries.exists():
        for entry in recent_entries:
            balance_effect = entry.debit_amount - entry.credit_amount
            print(f"  {entry.transaction_date}: DR {entry.debit_amount:,.2f} / CR {entry.credit_amount:,.2f} "
                  f"(Net: {balance_effect:+,.2f}) - Ref: {entry.reference_number or 'N/A'} - {entry.description[:50]}")
    else:
        print("  No entries found")

print(f"\n{'='*80}")
print("ANALYSIS COMPLETE")
print(f"{'='*80}")
