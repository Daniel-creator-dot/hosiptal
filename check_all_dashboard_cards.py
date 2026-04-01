"""
Check All Dashboard Cards - Revenue, AR, Account Balances
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting import GeneralLedger, PaymentReceipt, Account
from hospital.models_accounting_advanced import AdvancedAccountsReceivable
from django.db.models import Sum
from django.utils import timezone
from decimal import Decimal
from datetime import date

print("=" * 80)
print("CHECKING ALL DASHBOARD CARDS")
print("=" * 80)

today = timezone.now().date()
start_of_month = today.replace(day=1)

# 1. Today's Revenue
print("\n1. TODAY'S REVENUE:")
print("-" * 80)

# From General Ledger
today_revenue_gl = GeneralLedger.objects.filter(
    account__account_type='revenue',
    transaction_date=today,
    is_deleted=False
).aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')

# From Payment Receipts
today_revenue_receipts = PaymentReceipt.objects.filter(
    receipt_date__date=today,
    is_deleted=False
).aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')

print(f"  From General Ledger: GHS {today_revenue_gl:,.2f}")
print(f"  From Payment Receipts: GHS {today_revenue_receipts:,.2f}")
print(f"  Using: GHS {today_revenue_gl if today_revenue_gl > 0 else today_revenue_receipts:,.2f}")

# 2. Monthly Revenue
print("\n2. MONTHLY REVENUE (This Month):")
print("-" * 80)

# From General Ledger
month_revenue_gl = GeneralLedger.objects.filter(
    account__account_type='revenue',
    transaction_date__gte=start_of_month,
    transaction_date__lte=today,
    is_deleted=False
).aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')

# From Payment Receipts
month_revenue_receipts = PaymentReceipt.objects.filter(
    receipt_date__date__gte=start_of_month,
    receipt_date__date__lte=today,
    is_deleted=False
).aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')

print(f"  Period: {start_of_month.strftime('%B %d')} to {today.strftime('%B %d, %Y')}")
print(f"  From General Ledger: GHS {month_revenue_gl:,.2f}")
print(f"  From Payment Receipts: GHS {month_revenue_receipts:,.2f}")
print(f"  Using: GHS {month_revenue_gl if month_revenue_gl > 0 else month_revenue_receipts:,.2f}")

# 3. Accounts Receivable
print("\n3. ACCOUNTS RECEIVABLE:")
print("-" * 80)

ar_total = AdvancedAccountsReceivable.objects.filter(
    balance_due__gt=0,
    is_deleted=False
).aggregate(Sum('balance_due'))['balance_due__sum'] or Decimal('0.00')

ar_count = AdvancedAccountsReceivable.objects.filter(
    balance_due__gt=0,
    is_deleted=False
).count()

print(f"  Total AR: GHS {ar_total:,.2f}")
print(f"  Number of AR entries: {ar_count}")

if ar_count > 0:
    print(f"\n  AR Entries:")
    for ar in AdvancedAccountsReceivable.objects.filter(balance_due__gt=0, is_deleted=False)[:5]:
        print(f"    - {ar.invoice.invoice_number if ar.invoice else 'N/A'}: GHS {ar.balance_due:,.2f}")

# 4. Account Balances (Key Accounts)
print("\n4. KEY ACCOUNT BALANCES:")
print("-" * 80)

key_accounts = Account.objects.filter(
    account_code__in=['1010', '4010', '4020', '4030', '4040', '4060'],
    is_deleted=False
)

for account in key_accounts:
    gl_entries = GeneralLedger.objects.filter(
        account=account,
        is_deleted=False
    ).aggregate(
        total_debits=Sum('debit_amount'),
        total_credits=Sum('credit_amount')
    )
    
    total_debits = gl_entries['total_debits'] or Decimal('0.00')
    total_credits = gl_entries['total_credits'] or Decimal('0.00')
    
    if account.account_type in ['asset', 'expense']:
        balance = total_debits - total_credits
    else:
        balance = total_credits - total_debits
    
    print(f"  {account.account_code} - {account.account_name}: GHS {balance:,.2f}")

# 5. Revenue Breakdown by Account
print("\n5. REVENUE BREAKDOWN (This Month):")
print("-" * 80)

revenue_accounts = Account.objects.filter(
    account_type='revenue',
    account_code__in=['4010', '4020', '4030', '4040', '4060'],
    is_deleted=False
)

for account in revenue_accounts:
    revenue = GeneralLedger.objects.filter(
        account=account,
        transaction_date__gte=start_of_month,
        transaction_date__lte=today,
        is_deleted=False
    ).aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
    
    print(f"  {account.account_code} - {account.account_name}: GHS {revenue:,.2f}")

# 6. Summary
print("\n" + "=" * 80)
print("SUMMARY:")
print("=" * 80)
print(f"  Today's Revenue: GHS {today_revenue_gl if today_revenue_gl > 0 else today_revenue_receipts:,.2f}")
print(f"  Monthly Revenue: GHS {month_revenue_gl if month_revenue_gl > 0 else month_revenue_receipts:,.2f}")
print(f"  Accounts Receivable: GHS {ar_total:,.2f}")
print(f"  Cash Balance (1010): GHS {[b for a, b in [(acc.account_code, GeneralLedger.objects.filter(account=acc, is_deleted=False).aggregate(total_debits=Sum('debit_amount'), total_credits=Sum('credit_amount'))['total_debits'] or Decimal('0.00') - (GeneralLedger.objects.filter(account=acc, is_deleted=False).aggregate(total_debits=Sum('debit_amount'), total_credits=Sum('credit_amount'))['total_credits'] or Decimal('0.00'))) for acc in key_accounts if acc.account_code == '1010']][0] if any(acc.account_code == '1010' for acc in key_accounts) else Decimal('0.00'):,.2f}")

print("\n" + "=" * 80)
print("CHECK COMPLETE")
print("=" * 80)
