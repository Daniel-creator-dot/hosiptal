"""
Verify Accounts Payable Dashboard Calculation
Check if it correctly uses General Ledger or falls back to model
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
print("VERIFYING ACCOUNTS PAYABLE DASHBOARD CALCULATION")
print("=" * 80)

# Simulate dashboard calculation
total_payable = Decimal('0.00')

# Check General Ledger for AP accounts
ap_accounts = Account.objects.filter(
    account_type='liability',
    account_name__icontains='payable',
    is_deleted=False
)

print(f"\nFound {ap_accounts.count()} AP accounts in General Ledger:")
for acc in ap_accounts:
    print(f"  - {acc.account_code}: {acc.account_name}")

print(f"\n" + "=" * 80)
print("CALCULATING FROM GENERAL LEDGER:")
print("=" * 80)

for ap_account in ap_accounts:
    ap_gl_total = AdvancedGeneralLedger.objects.filter(
        account=ap_account,
        is_voided=False,
        is_deleted=False
    ).aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
    
    print(f"  {ap_account.account_code} - {ap_account.account_name}: GHS {ap_gl_total:,.2f}")
    total_payable += ap_gl_total

print(f"\n  Total from General Ledger: GHS {total_payable:,.2f}")

# If GL has no data, use AccountsPayable model
if total_payable == 0:
    print(f"\n" + "=" * 80)
    print("FALLBACK TO AccountsPayable MODEL:")
    print("=" * 80)
    
    ap_model_total = AccountsPayable.objects.filter(
        balance_due__gt=0,
        is_deleted=False
    ).aggregate(total=Sum('balance_due'))['total'] or Decimal('0.00')
    
    print(f"  Total from AccountsPayable model: GHS {ap_model_total:,.2f}")
    total_payable = ap_model_total

print(f"\n" + "=" * 80)
print("FINAL RESULT:")
print("=" * 80)
print(f"  Dashboard will show: GHS {total_payable:,.2f}")

if total_payable > 0:
    source = "General Ledger" if AdvancedGeneralLedger.objects.filter(
        account__in=ap_accounts,
        is_voided=False,
        is_deleted=False
    ).exists() else "AccountsPayable Model"
    print(f"  Source: {source}")

print("\n" + "=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)
