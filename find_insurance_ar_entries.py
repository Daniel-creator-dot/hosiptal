"""
Find all entries that might be related to Insurance Receivables
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
print("FINDING INSURANCE RECEIVABLES ENTRIES")
print("=" * 80)

# Check for entries with the exact amount from trial balance
target_amount = Decimal('1836602.62')
print(f"\n1. Searching for entries with amount: GHS {target_amount:,.2f}")
print("-" * 80)

entries_exact = GeneralLedger.objects.filter(
    Q(debit_amount=target_amount) | Q(credit_amount=target_amount),
    is_deleted=False
)

if entries_exact.exists():
    print(f"[FOUND] {entries_exact.count()} entries with exact amount:")
    for entry in entries_exact:
        print(f"  Entry {entry.entry_number}:")
        print(f"    Account: {entry.account.account_code} - {entry.account.account_name} ({entry.account.account_type})")
        print(f"    DR: {entry.debit_amount:,.2f} / CR: {entry.credit_amount:,.2f}")
        print(f"    Date: {entry.transaction_date}")
        print(f"    Ref: {entry.reference_number or 'N/A'}")
        print(f"    Description: {entry.description[:100]}")
else:
    print("[OK] No entries found with exact amount")

# Check for entries with similar large amounts
print(f"\n\n2. Searching for entries with large amounts (> GHS 1,000,000):")
print("-" * 80)

large_entries = GeneralLedger.objects.filter(
    (Q(debit_amount__gt=1000000) | Q(credit_amount__gt=1000000)),
    is_deleted=False
).order_by('-debit_amount', '-credit_amount')

if large_entries.exists():
    print(f"[FOUND] {large_entries.count()} entries with large amounts:")
    for entry in large_entries[:20]:
        amount = max(entry.debit_amount, entry.credit_amount)
        print(f"  Entry {entry.entry_number}:")
        print(f"    Account: {entry.account.account_code} - {entry.account.account_name} ({entry.account.account_type})")
        print(f"    DR: {entry.debit_amount:,.2f} / CR: {entry.credit_amount:,.2f}")
        print(f"    Date: {entry.transaction_date}")
        print(f"    Ref: {entry.reference_number or 'N/A'}")
else:
    print("[OK] No entries found with large amounts")

# Check all accounts for entries mentioning insurance
print(f"\n\n3. Checking accounts with 'insurance' in name or description:")
print("-" * 80)

insurance_accounts = Account.objects.filter(
    (Q(account_name__icontains='insurance') | Q(account_name__icontains='receivable')),
    is_deleted=False
).order_by('account_code')

for account in insurance_accounts:
    entries = GeneralLedger.objects.filter(
        account=account,
        is_deleted=False
    )
    
    if entries.exists():
        debits = entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
        credits = entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
        balance = debits - credits if account.account_type in ['asset', 'expense'] else credits - debits
        
        print(f"\n{account.account_code} - {account.account_name} ({account.account_type})")
        print(f"  Entries: {entries.count()}")
        print(f"  Balance: GHS {balance:,.2f}")
        
        if balance > 1000:
            print(f"  [LARGE BALANCE] Recent entries:")
            for entry in entries.order_by('-transaction_date', '-created')[:5]:
                print(f"    - {entry.transaction_date}: DR {entry.debit_amount:,.2f} / CR {entry.credit_amount:,.2f} "
                      f"(Ref: {entry.reference_number or 'N/A'})")

# Check for entries with insurance-related reference numbers
print(f"\n\n4. Checking entries with insurance-related reference numbers:")
print("-" * 80)

insurance_refs = GeneralLedger.objects.filter(
    (Q(reference_number__icontains='insurance') | 
     Q(reference_number__icontains='claim') |
     Q(reference_number__icontains='AR') |
     Q(description__icontains='insurance')),
    is_deleted=False
).order_by('-transaction_date')[:20]

if insurance_refs.exists():
    print(f"[FOUND] {insurance_refs.count()} entries with insurance-related references:")
    for entry in insurance_refs:
        print(f"  Entry {entry.entry_number}:")
        print(f"    Account: {entry.account.account_code} - {entry.account.account_name}")
        print(f"    DR: {entry.debit_amount:,.2f} / CR: {entry.credit_amount:,.2f}")
        print(f"    Date: {entry.transaction_date}")
        print(f"    Ref: {entry.reference_number or 'N/A'}")
        print(f"    Desc: {entry.description[:80]}")
else:
    print("[OK] No entries found with insurance-related references")

# Check what account 1201 actually is
print(f"\n\n5. Checking account 1201 details:")
print("-" * 80)

account_1201 = Account.objects.filter(account_code='1201', is_deleted=False).first()
if account_1201:
    print(f"Account: {account_1201.account_code} - {account_1201.account_name}")
    print(f"Type: {account_1201.account_type}")
    print(f"Active: {account_1201.is_active}")
    print(f"Deleted: {account_1201.is_deleted}")
    
    entries = GeneralLedger.objects.filter(account=account_1201, is_deleted=False)
    print(f"Entries: {entries.count()}")
    
    if entries.exists():
        debits = entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
        credits = entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
        balance = debits - credits
        print(f"Debits: GHS {debits:,.2f}")
        print(f"Credits: GHS {credits:,.2f}")
        print(f"Balance: GHS {balance:,.2f}")
else:
    print("[WARNING] Account 1201 not found!")
