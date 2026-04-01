"""
Find where Accounts Payable amount GHS 600,834.40 is coming from
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

# Try to import AdvancedGeneralLedger
try:
    from hospital.models_accounting_advanced import AdvancedGeneralLedger
    HAS_ADVANCED = True
except ImportError:
    HAS_ADVANCED = False

print("=" * 80)
print("FINDING ACCOUNTS PAYABLE SOURCE")
print("=" * 80)

target_amount = Decimal('600834.40')
print(f"\nSearching for Accounts Payable balance: GHS {target_amount:,.2f}\n")

# Check all liability accounts
liability_accounts = Account.objects.filter(
    account_type='liability',
    is_deleted=False
).order_by('account_code')

print("Checking all liability accounts:")
print("-" * 80)

total_liability = Decimal('0.00')
for account in liability_accounts:
    # GeneralLedger
    gl_entries = GeneralLedger.objects.filter(account=account, is_deleted=False)
    gl_debits = gl_entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
    gl_credits = gl_entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
    
    # AdvancedGeneralLedger
    adv_debits = Decimal('0.00')
    adv_credits = Decimal('0.00')
    if HAS_ADVANCED:
        adv_entries = AdvancedGeneralLedger.objects.filter(
            account=account,
            is_voided=False,
            is_deleted=False
        )
        adv_debits = adv_entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
        adv_credits = adv_entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
    
    # Combined
    total_debits = gl_debits + adv_debits
    total_credits = gl_credits + adv_credits
    balance = total_credits - total_debits  # Liability balance
    
    if balance != 0 or gl_entries.exists() or (HAS_ADVANCED and adv_entries.exists()):
        print(f"\n{account.account_code} - {account.account_name}")
        print(f"  GL Entries: {gl_entries.count()}, Debits: {gl_debits:,.2f}, Credits: {gl_credits:,.2f}")
        if HAS_ADVANCED:
            print(f"  Adv Entries: {adv_entries.count()}, Debits: {adv_debits:,.2f}, Credits: {adv_credits:,.2f}")
        print(f"  Total Balance: GHS {balance:,.2f}")
        
        if abs(balance - target_amount) < Decimal('0.01'):
            print(f"  [MATCH] This account matches the target amount!")
        
        total_liability += balance

print(f"\n{'='*80}")
print(f"TOTAL LIABILITIES: GHS {total_liability:,.2f}")
print(f"{'='*80}")

# Check if target amount is a sum of multiple accounts
if abs(total_liability - target_amount) < Decimal('0.01'):
    print(f"\n[MATCH] Total liabilities matches target amount!")
elif total_liability > 0:
    print(f"\n[INFO] Total liabilities: GHS {total_liability:,.2f}")
    print(f"        Target amount:    GHS {target_amount:,.2f}")
    print(f"        Difference:       GHS {abs(total_liability - target_amount):,.2f}")

# Check for entries with exact amount
print(f"\n\nSearching for entries with exact amount GHS {target_amount:,.2f}:")
print("-" * 80)

matching_entries = GeneralLedger.objects.filter(
    is_deleted=False
).filter(Q(debit_amount=target_amount) | Q(credit_amount=target_amount))

if matching_entries.exists():
    print(f"[FOUND] {matching_entries.count()} entries with exact amount:")
    for entry in matching_entries:
        print(f"  Account: {entry.account.account_code} - {entry.account.account_name}")
        print(f"  DR: {entry.debit_amount:,.2f} / CR: {entry.credit_amount:,.2f}")
        print(f"  Date: {entry.transaction_date}, Ref: {entry.reference_number or 'N/A'}")
else:
    print("[OK] No entries found with exact amount")

if HAS_ADVANCED:
    adv_matching = AdvancedGeneralLedger.objects.filter(
        is_voided=False,
        is_deleted=False
    ).filter(Q(debit_amount=target_amount) | Q(credit_amount=target_amount))
    
    if adv_matching.exists():
        print(f"\n[FOUND] {adv_matching.count()} AdvancedGeneralLedger entries with exact amount:")
        for entry in adv_matching:
            print(f"  Account: {entry.account.account_code} - {entry.account.account_name}")
            print(f"  DR: {entry.debit_amount:,.2f} / CR: {entry.credit_amount:,.2f}")
            print(f"  Date: {entry.transaction_date}")
