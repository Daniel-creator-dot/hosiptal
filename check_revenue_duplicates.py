"""
Check for duplicate revenue entries in GeneralLedger
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting import GeneralLedger, Account
from django.db.models import Count, Sum, Q
from decimal import Decimal
from collections import defaultdict

print("=" * 80)
print("CHECKING FOR DUPLICATE REVENUE ENTRIES")
print("=" * 80)

# Get all revenue accounts
revenue_accounts = Account.objects.filter(account_type='revenue', is_deleted=False)
print(f"\nFound {revenue_accounts.count()} revenue accounts\n")

total_duplicates = 0
total_duplicate_amount = Decimal('0.00')

for account in revenue_accounts:
    print(f"\n{'='*80}")
    print(f"Account: {account.account_code} - {account.account_name}")
    print(f"{'='*80}")
    
    # Get all credit entries for this revenue account
    entries = GeneralLedger.objects.filter(
        account=account,
        credit_amount__gt=0,
        is_deleted=False
    ).order_by('reference_number', 'transaction_date', 'created')
    
    total_credits = entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
    entry_count = entries.count()
    
    print(f"Total entries: {entry_count}")
    print(f"Total credits: GHS {total_credits:,.2f}")
    
    # Check for duplicates by reference_number
    duplicates_by_ref = defaultdict(list)
    for entry in entries:
        if entry.reference_number:
            duplicates_by_ref[entry.reference_number].append(entry)
    
    # Find reference numbers with multiple entries
    duplicate_refs = {ref: entries_list for ref, entries_list in duplicates_by_ref.items() 
                     if len(entries_list) > 1}
    
    if duplicate_refs:
        print(f"\n[WARNING] Found {len(duplicate_refs)} reference numbers with duplicates:")
        for ref_num, dup_entries in duplicate_refs.items():
            total_dup_amount = sum(e.credit_amount for e in dup_entries)
            print(f"\n  Reference: {ref_num}")
            print(f"  Duplicate count: {len(dup_entries)}")
            print(f"  Total amount: GHS {total_dup_amount:,.2f}")
            print(f"  Expected amount: GHS {total_dup_amount / len(dup_entries):,.2f}")
            
            for i, entry in enumerate(dup_entries, 1):
                print(f"    {i}. Entry {entry.entry_number}: GHS {entry.credit_amount:,.2f} "
                      f"on {entry.transaction_date} (ID: {entry.pk})")
            
            total_duplicates += len(dup_entries) - 1  # One is correct, rest are duplicates
            total_duplicate_amount += total_dup_amount - (total_dup_amount / len(dup_entries))
    else:
        print("[OK] No duplicates found by reference number")
    
    # Check for duplicates by same amount, date, and account (without reference)
    print(f"\nChecking for entries with same amount and date (no reference)...")
    entries_no_ref = entries.filter(Q(reference_number='') | Q(reference_number__isnull=True))
    
    if entries_no_ref.exists():
        amount_date_groups = defaultdict(list)
        for entry in entries_no_ref:
            key = (entry.credit_amount, entry.transaction_date)
            amount_date_groups[key].append(entry)
        
        duplicate_groups = {key: entries_list for key, entries_list in amount_date_groups.items() 
                          if len(entries_list) > 1}
        
        if duplicate_groups:
            print(f"[WARNING] Found {len(duplicate_groups)} groups of duplicate entries (same amount & date, no reference):")
            for (amount, date), dup_entries in duplicate_groups.items():
                print(f"\n  Amount: GHS {amount:,.2f}, Date: {date}")
                print(f"  Duplicate count: {len(dup_entries)}")
                for i, entry in enumerate(dup_entries, 1):
                    print(f"    {i}. Entry {entry.entry_number}: ID {entry.pk}, Created: {entry.created}")
                
                total_duplicates += len(dup_entries) - 1
                total_duplicate_amount += amount * (len(dup_entries) - 1)
        else:
            print("[OK] No duplicates found by amount/date")
    
    # Check for exact duplicates (same everything)
    print(f"\nChecking for exact duplicate entries...")
    exact_duplicates = GeneralLedger.objects.filter(
        account=account,
        credit_amount__gt=0,
        is_deleted=False
    ).values(
        'reference_number', 'transaction_date', 'credit_amount', 'debit_amount', 'description'
    ).annotate(
        count=Count('id')
    ).filter(count__gt=1)
    
    if exact_duplicates.exists():
        print(f"[WARNING] Found {exact_duplicates.count()} groups of exact duplicates:")
        for dup in exact_duplicates:
            print(f"  Ref: {dup['reference_number']}, Date: {dup['transaction_date']}, "
                  f"Amount: GHS {dup['credit_amount']:,.2f}, Count: {dup['count']}")
            total_duplicates += dup['count'] - 1
            total_duplicate_amount += dup['credit_amount'] * (dup['count'] - 1)
    else:
        print("[OK] No exact duplicates found")

print(f"\n{'='*80}")
print("SUMMARY")
print(f"{'='*80}")
print(f"Total duplicate entries found: {total_duplicates}")
print(f"Total duplicate amount: GHS {total_duplicate_amount:,.2f}")
print(f"{'='*80}")

if total_duplicates > 0:
    print("\n[WARNING] ACTION REQUIRED: Duplicate entries detected!")
    print("   Run: python manage.py fix_accounting_duplicates --dry-run")
    print("   Then: python manage.py fix_accounting_duplicates")
else:
    print("\n[OK] No duplicates found - revenue figures are correct!")
