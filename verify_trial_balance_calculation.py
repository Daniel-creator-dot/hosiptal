"""
Verify trial balance calculation matches what we expect
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting import GeneralLedger, Account
from django.db.models import Sum
from django.utils import timezone
from decimal import Decimal

print("=" * 80)
print("TRIAL BALANCE CALCULATION VERIFICATION")
print("=" * 80)

report_date = timezone.now().date()
print(f"\nReport Date: {report_date}\n")

accounts_list = Account.objects.filter(is_active=True, is_deleted=False).order_by('account_code')

accounts_with_balance = []
total_debits = Decimal('0.00')
total_credits = Decimal('0.00')

print("Accounts with activity:")
print("-" * 80)

for account in accounts_list:
    entries = GeneralLedger.objects.filter(
        account=account,
        transaction_date__lte=report_date,
        is_deleted=False
    )
    
    debits = entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
    credits = entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
    
    # Calculate balance based on account type
    if account.account_type in ['asset', 'expense']:
        balance = debits - credits
    else:
        balance = credits - debits
    
    # Only include accounts with activity
    if debits > 0 or credits > 0:
        accounts_with_balance.append({
            'account': account,
            'debits': debits,
            'credits': credits,
            'balance': balance
        })
        
        total_debits += debits
        total_credits += credits
        
        # Show account details
        print(f"\n{account.account_code} - {account.account_name} ({account.account_type})")
        print(f"  Debits:  GHS {debits:,.2f}")
        print(f"  Credits: GHS {credits:,.2f}")
        print(f"  Balance: GHS {balance:,.2f} (should show in {'DEBIT' if balance >= 0 and account.account_type in ['asset', 'expense'] else 'CREDIT'} column)")
        
        if account.account_code == '1201':
            print(f"  [INSURANCE RECEIVABLES] Entry count: {entries.count()}")
            if entries.exists():
                print(f"  Entries:")
                for entry in entries.order_by('transaction_date', 'created'):
                    print(f"    - {entry.transaction_date}: DR {entry.debit_amount:,.2f} / CR {entry.credit_amount:,.2f} "
                          f"(Ref: {entry.reference_number or 'N/A'}, Entry: {entry.entry_number})")

balance_difference = total_debits - total_credits

print(f"\n{'='*80}")
print("TRIAL BALANCE TOTALS")
print(f"{'='*80}")
print(f"Total Debits:  GHS {total_debits:,.2f}")
print(f"Total Credits: GHS {total_credits:,.2f}")
print(f"Difference:    GHS {balance_difference:,.2f}")
print(f"Balanced:      {'YES' if balance_difference == 0 else 'NO'}")

# Check specifically for account 1201
print(f"\n{'='*80}")
print("SPECIFIC CHECK: Account 1201 (Insurance Receivables)")
print(f"{'='*80}")

account_1201 = Account.objects.filter(account_code='1201', is_deleted=False).first()
if account_1201:
    entries_1201 = GeneralLedger.objects.filter(
        account=account_1201,
        transaction_date__lte=report_date,
        is_deleted=False
    )
    
    debits_1201 = entries_1201.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
    credits_1201 = entries_1201.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
    balance_1201 = debits_1201 - credits_1201
    
    print(f"Account: {account_1201.account_code} - {account_1201.account_name}")
    print(f"Type: {account_1201.account_type}")
    print(f"Entries: {entries_1201.count()}")
    print(f"Debits: GHS {debits_1201:,.2f}")
    print(f"Credits: GHS {credits_1201:,.2f}")
    print(f"Balance: GHS {balance_1201:,.2f}")
    
    if balance_1201 == 0 and entries_1201.count() == 0:
        print("\n[OK] Account 1201 has no entries and zero balance - this is correct!")
    elif balance_1201 != 0:
        print(f"\n[WARNING] Account 1201 has balance of GHS {balance_1201:,.2f}")
        print("This should match what's shown in trial balance.")
else:
    print("[ERROR] Account 1201 not found!")
