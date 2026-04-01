"""
Check Accounts Payable and Insurance Receivables for errors
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
print("ACCOUNTS PAYABLE & INSURANCE RECEIVABLES CHECK")
print("=" * 80)

# Check Accounts Payable (2000)
print("\n" + "=" * 80)
print("ACCOUNTS PAYABLE (2000)")
print("=" * 80)

ap_account = Account.objects.filter(account_code='2000', is_deleted=False).first()
if not ap_account:
    print("[ERROR] Account 2000 (Accounts Payable) not found!")
    # Try to find similar accounts
    similar = Account.objects.filter(
        Q(account_name__icontains='payable') | Q(account_name__icontains='payable'),
        account_type='liability',
        is_deleted=False
    )
    if similar.exists():
        print(f"\nFound {similar.count()} similar liability accounts:")
        for acc in similar:
            print(f"  {acc.account_code} - {acc.account_name}")
else:
    print(f"\nAccount: {ap_account.account_code} - {ap_account.account_name}")
    print(f"Type: {ap_account.account_type}")
    print(f"Active: {ap_account.is_active}")
    
    # Get all entries
    all_entries = GeneralLedger.objects.filter(account=ap_account)
    active_entries = GeneralLedger.objects.filter(account=ap_account, is_deleted=False)
    
    # Calculate totals
    all_debits = all_entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
    all_credits = all_entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
    
    active_debits = active_entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
    active_credits = active_entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
    
    # Liability balance = credits - debits
    all_balance = all_credits - all_debits
    active_balance = active_credits - active_debits
    
    deleted_count = all_entries.filter(is_deleted=True).count()
    
    print(f"\nSummary:")
    print(f"  Active entries: {active_entries.count()}")
    print(f"  Deleted entries: {deleted_count}")
    print(f"  Active Debits:  GHS {active_debits:,.2f}")
    print(f"  Active Credits: GHS {active_credits:,.2f}")
    print(f"  Active Balance: GHS {active_balance:,.2f} (should be positive for liability)")
    
    if deleted_count > 0:
        print(f"\n[WARNING] Has {deleted_count} deleted entries")
        print(f"  All Debits:  GHS {all_debits:,.2f}")
        print(f"  All Credits: GHS {all_credits:,.2f}")
        print(f"  All Balance: GHS {all_balance:,.2f}")
    
    # Check for duplicate entries
    print(f"\n\n1. Checking for duplicate entries...")
    print("-" * 80)
    
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
            dup_amount = total_dup_credits - total_dup_debits
            print(f"\n  Reference: {ref_num}")
            print(f"  Duplicate count: {len(entries)}")
            print(f"  Total Debits: GHS {total_dup_debits:,.2f}")
            print(f"  Total Credits: GHS {total_dup_credits:,.2f}")
            print(f"  Net Amount: GHS {dup_amount:,.2f}")
            for i, entry in enumerate(entries, 1):
                print(f"    {i}. Entry {entry.entry_number}: DR {entry.debit_amount:,.2f} / CR {entry.credit_amount:,.2f} "
                      f"on {entry.transaction_date} (ID: {entry.pk})")
            total_dup_amount += dup_amount * (len(entries) - 1)
        print(f"\n  Estimated duplicate amount: GHS {total_dup_amount:,.2f}")
    else:
        print("[OK] No duplicates found by reference number")
    
    # Show recent entries
    print(f"\n\n2. Recent Entries (last 10):")
    print("-" * 80)
    
    recent_entries = active_entries.order_by('-transaction_date', '-created')[:10]
    if recent_entries.exists():
        for entry in recent_entries:
            balance_effect = entry.credit_amount - entry.debit_amount
            print(f"  {entry.transaction_date}: DR {entry.debit_amount:,.2f} / CR {entry.credit_amount:,.2f} "
                  f"(Net: {balance_effect:+,.2f}) - Ref: {entry.reference_number or 'N/A'} - {entry.description[:50]}")
    else:
        print("  No entries found")

# Check Insurance Receivables (1201)
print("\n\n" + "=" * 80)
print("INSURANCE RECEIVABLES (1201)")
print("=" * 80)

ir_account = Account.objects.filter(account_code='1201', is_deleted=False).first()
if not ir_account:
    print("[ERROR] Account 1201 (Insurance Receivables) not found!")
else:
    print(f"\nAccount: {ir_account.account_code} - {ir_account.account_name}")
    print(f"Type: {ir_account.account_type}")
    print(f"Active: {ir_account.is_active}")
    
    # Get all entries
    all_entries = GeneralLedger.objects.filter(account=ir_account)
    active_entries = GeneralLedger.objects.filter(account=ir_account, is_deleted=False)
    
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
    
    # Check if balance matches the displayed amount
    displayed_amount = Decimal('1836602.62')
    if abs(active_balance - displayed_amount) < Decimal('0.01'):
        print(f"\n[MATCH] Balance matches displayed amount: GHS {displayed_amount:,.2f}")
    elif active_balance != displayed_amount:
        print(f"\n[MISMATCH] Balance does not match displayed amount!")
        print(f"  Calculated Balance: GHS {active_balance:,.2f}")
        print(f"  Displayed Amount:   GHS {displayed_amount:,.2f}")
        print(f"  Difference:         GHS {abs(active_balance - displayed_amount):,.2f}")
    
    if deleted_count > 0:
        print(f"\n[WARNING] Has {deleted_count} deleted entries")
        print(f"  All Debits:  GHS {all_debits:,.2f}")
        print(f"  All Credits: GHS {all_credits:,.2f}")
        print(f"  All Balance: GHS {all_balance:,.2f}")
    
    # Check for duplicate entries
    print(f"\n\n1. Checking for duplicate entries...")
    print("-" * 80)
    
    ref_groups = defaultdict(list)
    for entry in active_entries:
        if entry.reference_number:
            ref_groups[entry.reference_number].append(entry)
    
    duplicate_refs = {ref: entries for ref, entries in ref_groups.items() if len(entries) > 1}
    
    if duplicate_refs:
        print(f"[WARNING] Found {len(duplicate_refs)} reference numbers with multiple entries:")
        for ref_num, entries in list(duplicate_refs.items())[:10]:
            print(f"\n  Reference: {ref_num}")
            print(f"  Duplicate count: {len(entries)}")
            for i, entry in enumerate(entries, 1):
                print(f"    {i}. Entry {entry.entry_number}: DR {entry.debit_amount:,.2f} / CR {entry.credit_amount:,.2f} "
                      f"on {entry.transaction_date} (ID: {entry.pk})")
    else:
        print("[OK] No duplicates found by reference number")
    
    # Show all entries if any
    print(f"\n\n2. All Entries:")
    print("-" * 80)
    
    if active_entries.exists():
        for entry in active_entries.order_by('transaction_date', 'created'):
            balance_effect = entry.debit_amount - entry.credit_amount
            print(f"  {entry.transaction_date}: DR {entry.debit_amount:,.2f} / CR {entry.credit_amount:,.2f} "
                  f"(Net: {balance_effect:+,.2f}) - Ref: {entry.reference_number or 'N/A'} - {entry.description[:60]}")
    else:
        print("  [INFO] No entries found - account should show zero balance")

# Check all liability accounts for Accounts Payable
print("\n\n" + "=" * 80)
print("ALL LIABILITY ACCOUNTS (2000-2999)")
print("=" * 80)

liability_accounts = Account.objects.filter(
    account_code__startswith='2',
    account_type='liability',
    is_deleted=False
).order_by('account_code')

total_liability = Decimal('0.00')
for account in liability_accounts:
    entries = GeneralLedger.objects.filter(account=account, is_deleted=False)
    debits = entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
    credits = entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
    balance = credits - debits
    
    if entries.exists() or balance != 0:
        print(f"\n{account.account_code} - {account.account_name}")
        print(f"  Entries: {entries.count()}")
        print(f"  Debits:  GHS {debits:,.2f}")
        print(f"  Credits: GHS {credits:,.2f}")
        print(f"  Balance: GHS {balance:,.2f}")
        total_liability += balance

print(f"\n{'='*80}")
print(f"TOTAL LIABILITIES: GHS {total_liability:,.2f}")
print(f"{'='*80}")

print("\n" + "=" * 80)
print("CHECK COMPLETE")
print("=" * 80)
