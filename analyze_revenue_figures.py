"""
Detailed analysis of revenue figures to identify discrepancies
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
print("DETAILED REVENUE FIGURES ANALYSIS")
print("=" * 80)

# Get all revenue accounts
revenue_accounts = Account.objects.filter(account_type='revenue', is_deleted=False).order_by('account_code')

print("\nRevenue Accounts Summary:")
print("-" * 80)
total_revenue = Decimal('0.00')

for account in revenue_accounts:
    # Get all entries
    entries = GeneralLedger.objects.filter(
        account=account,
        is_deleted=False
    )
    
    total_debits = entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
    total_credits = entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
    
    # Revenue balance = credits - debits
    balance = total_credits - total_debits
    
    print(f"\n{account.account_code} - {account.account_name}")
    print(f"  Total Debits:  GHS {total_debits:,.2f}")
    print(f"  Total Credits: GHS {total_credits:,.2f}")
    print(f"  Net Balance:  GHS {balance:,.2f}")
    print(f"  Entry Count:  {entries.count()}")
    
    if entries.exists():
        print(f"  Recent Entries:")
        for entry in entries.order_by('-transaction_date', '-created')[:5]:
            print(f"    - {entry.transaction_date}: CR GHS {entry.credit_amount:,.2f} / DR GHS {entry.debit_amount:,.2f} "
                  f"(Ref: {entry.reference_number or 'N/A'})")
    
    total_revenue += balance

print(f"\n{'='*80}")
print(f"TOTAL REVENUE (All Accounts): GHS {total_revenue:,.2f}")
print(f"{'='*80}")

# Check for entries with same reference number across different accounts
print("\n\nChecking for cross-account duplicates (same reference, different accounts)...")
print("-" * 80)

# Group by reference number
from collections import defaultdict
ref_groups = defaultdict(list)

all_revenue_entries = GeneralLedger.objects.filter(
    account__account_type='revenue',
    is_deleted=False,
    reference_number__isnull=False
).exclude(reference_number='')

for entry in all_revenue_entries:
    if entry.reference_number:
        ref_groups[entry.reference_number].append(entry)

duplicate_refs = {ref: entries for ref, entries in ref_groups.items() if len(entries) > 1}

if duplicate_refs:
    print(f"[WARNING] Found {len(duplicate_refs)} reference numbers appearing in multiple revenue accounts:")
    for ref_num, entries in list(duplicate_refs.items())[:10]:  # Show first 10
        accounts = set(e.account.account_code for e in entries)
        if len(accounts) > 1:
            print(f"\n  Reference: {ref_num}")
            print(f"  Appears in {len(accounts)} different accounts: {', '.join(accounts)}")
            total_amount = sum(e.credit_amount for e in entries)
            print(f"  Total amount across all: GHS {total_amount:,.2f}")
            for entry in entries:
                print(f"    - {entry.account.account_code}: GHS {entry.credit_amount:,.2f} on {entry.transaction_date}")
else:
    print("[OK] No cross-account duplicates found")

# Check trial balance calculation
print("\n\nTrial Balance Calculation Check:")
print("-" * 80)
print("How trial balance calculates revenue:")
print("  For revenue accounts: balance = credits - debits")
print("  Positive balance should show in CREDIT column")
print("  Negative balance should show in DEBIT column")

for account in revenue_accounts:
    entries = GeneralLedger.objects.filter(
        account=account,
        is_deleted=False
    )
    
    total_debits = entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
    total_credits = entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
    
    # Trial balance calculation (as per fixed view)
    balance = total_credits - total_debits
    
    print(f"\n{account.account_code} - {account.account_name}:")
    print(f"  Calculated Balance: GHS {balance:,.2f}")
    if balance >= 0:
        print(f"  Should appear in: CREDIT column (GHS {balance:,.2f})")
    else:
        print(f"  Should appear in: DEBIT column (GHS {abs(balance):,.2f})")
