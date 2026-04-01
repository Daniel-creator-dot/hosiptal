"""
Find Any Accounts Payable Data in General Ledger
Check all accounts for AP-related entries
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting_advanced import AdvancedGeneralLedger
from hospital.models_accounting import Account
from django.db.models import Sum
from decimal import Decimal

print("=" * 80)
print("SEARCHING FOR ANY AP DATA IN GENERAL LEDGER")
print("=" * 80)

# Search for any entries with "payable" in description
print("\n1. Searching entries with 'payable' in description:")
print("-" * 80)

ap_entries = AdvancedGeneralLedger.objects.filter(
    description__icontains='payable',
    is_voided=False,
    is_deleted=False
).select_related('account')

print(f"  Found {ap_entries.count()} entries with 'payable' in description")

if ap_entries.count() > 0:
    total = Decimal('0.00')
    for entry in ap_entries[:20]:
        balance = entry.debit_amount if entry.debit_amount > 0 else entry.credit_amount
        total += balance
        print(f"    - {entry.account.account_code} - {entry.account.account_name}")
        print(f"      Description: {entry.description[:60]}")
        print(f"      Debit: GHS {entry.debit_amount:,.2f}, Credit: GHS {entry.credit_amount:,.2f}")
        print(f"      Balance: GHS {balance:,.2f}")
    print(f"\n  Total from these entries: GHS {total:,.2f}")

# Check all liability accounts
print("\n2. Checking ALL liability accounts:")
print("-" * 80)

liability_accounts = Account.objects.filter(
    account_type='liability',
    is_deleted=False
).order_by('account_code')

total_liability_debits = Decimal('0.00')
accounts_with_data = []

for account in liability_accounts:
    gl_entries = AdvancedGeneralLedger.objects.filter(
        account=account,
        is_voided=False,
        is_deleted=False
    )
    
    debit_total = gl_entries.aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
    
    if gl_entries.count() > 0:
        accounts_with_data.append({
            'account': account,
            'debit_total': debit_total,
            'count': gl_entries.count()
        })
        total_liability_debits += debit_total
        print(f"  {account.account_code} - {account.account_name}:")
        print(f"    Entries: {gl_entries.count()}, Total Debits: GHS {debit_total:,.2f}")

print(f"\n  Total from all liability accounts (debit amounts): GHS {total_liability_debits:,.2f}")
print(f"  Accounts with data: {len(accounts_with_data)}")

# Check recent GL entries
print("\n3. Recent General Ledger entries (last 50):")
print("-" * 80)

recent_entries = AdvancedGeneralLedger.objects.filter(
    is_voided=False,
    is_deleted=False
).select_related('account').order_by('-transaction_date', '-created')[:50]

print(f"  Showing {recent_entries.count()} recent entries")
for entry in recent_entries[:10]:
    if entry.debit_amount > 0 or entry.credit_amount > 0:
        print(f"    - {entry.transaction_date} | {entry.account.account_code} - {entry.account.account_name}")
        print(f"      Description: {entry.description[:60]}")
        print(f"      Debit: GHS {entry.debit_amount:,.2f}, Credit: GHS {entry.credit_amount:,.2f}")

print("\n" + "=" * 80)
print("SEARCH COMPLETE")
print("=" * 80)
