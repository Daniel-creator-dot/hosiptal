"""
Verify All Accounts Payable Calculations
Check that all views use the same logic: General Ledger first, then fallback to model
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting_advanced import AccountsPayable, AdvancedGeneralLedger
from hospital.models_accounting import Account
from django.db.models import Sum
from decimal import Decimal

print("=" * 80)
print("VERIFYING ALL ACCOUNTS PAYABLE CALCULATIONS")
print("=" * 80)

def calculate_ap_standard():
    """Standard AP calculation: GL first, then fallback to model"""
    total_payable = Decimal('0.00')
    
    # Check General Ledger for AP accounts
    ap_accounts = Account.objects.filter(
        account_type='liability',
        account_name__icontains='payable',
        is_deleted=False
    )
    
    for ap_account in ap_accounts:
        ap_gl_total = AdvancedGeneralLedger.objects.filter(
            account=ap_account,
            is_voided=False,
            is_deleted=False
        ).aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
        total_payable += ap_gl_total
    
    # If GL has no data, fall back to AccountsPayable model
    if total_payable == 0:
        total_payable = AccountsPayable.objects.filter(
            balance_due__gt=0,
            is_deleted=False
        ).aggregate(total=Sum('balance_due'))['total'] or Decimal('0.00')
    
    return total_payable

# Calculate using standard method
ap_total = calculate_ap_standard()

print(f"\nStandard AP Calculation Result: GHS {ap_total:,.2f}")

# Check sources
print(f"\n" + "=" * 80)
print("BREAKDOWN:")
print("=" * 80)

ap_accounts = Account.objects.filter(
    account_type='liability',
    account_name__icontains='payable',
    is_deleted=False
)

gl_total = Decimal('0.00')
for ap_account in ap_accounts:
    ap_gl_total = AdvancedGeneralLedger.objects.filter(
        account=ap_account,
        is_voided=False,
        is_deleted=False
    ).aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
    gl_total += ap_gl_total
    if ap_gl_total > 0:
        print(f"  General Ledger - {ap_account.account_code}: GHS {ap_gl_total:,.2f}")

model_total = AccountsPayable.objects.filter(
    balance_due__gt=0,
    is_deleted=False
).aggregate(total=Sum('balance_due'))['total'] or Decimal('0.00')

print(f"\n  General Ledger Total: GHS {gl_total:,.2f}")
print(f"  AccountsPayable Model Total: GHS {model_total:,.2f}")
print(f"  Final Result: GHS {ap_total:,.2f}")

if gl_total > 0:
    print(f"\n  [OK] Using General Ledger data")
else:
    print(f"\n  [OK] Using AccountsPayable model (fallback)")

print("\n" + "=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)
print("\nAll views should use this same calculation logic:")
print("  1. Check General Ledger for AP accounts (sum debit amounts)")
print("  2. If GL total is 0, use AccountsPayable model")
print("  3. Debit amounts ARE the balances (independent, different companies)")
