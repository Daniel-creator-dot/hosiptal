"""
Check Accounts Payable Balance Sources
Verify where GHS 600,834.40 is coming from
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
print("CHECKING ACCOUNTS PAYABLE BALANCE SOURCES")
print("=" * 80)

# Check AccountsPayable model
print("\n1. FROM AccountsPayable MODEL:")
print("-" * 80)
try:
    ap_entries = AccountsPayable.objects.filter(
        balance_due__gt=0,
        is_deleted=False
    )
    ap_total_from_model = ap_entries.aggregate(total=Sum('balance_due'))['total'] or Decimal('0.00')
    print(f"  Total from AccountsPayable model: GHS {ap_total_from_model:,.2f}")
    print(f"  Number of entries: {ap_entries.count()}")
    
    if ap_entries.count() > 0:
        print(f"\n  Sample entries:")
        for entry in ap_entries[:5]:
            print(f"    - {entry.vendor_name if hasattr(entry, 'vendor_name') else 'N/A'}: GHS {entry.balance_due:,.2f}")
except Exception as e:
    print(f"  Error: {e}")
    ap_total_from_model = Decimal('0.00')

# Check General Ledger for AP accounts
print("\n2. FROM GENERAL LEDGER (AP Accounts):")
print("-" * 80)

# Find AP account codes (typically 2000 series for liabilities)
ap_accounts = Account.objects.filter(
    account_type='liability',
    account_name__icontains='payable',
    is_deleted=False
).order_by('account_code')

print(f"  Found {ap_accounts.count()} AP accounts:")
for acc in ap_accounts:
    print(f"    - {acc.account_code}: {acc.account_name}")

# Get GL entries for AP accounts
ap_total_from_gl = Decimal('0.00')
for account in ap_accounts:
    gl_entries = AdvancedGeneralLedger.objects.filter(
        account=account,
        is_voided=False,
        is_deleted=False
    )
    
    # For Excel imports: debit amounts ARE the balances (independent)
    # Sum all debit amounts (each is an independent balance)
    account_total = gl_entries.aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
    
    if account_total > 0:
        print(f"\n  {account.account_code} - {account.account_name}:")
        print(f"    Total from GL (sum of debit amounts): GHS {account_total:,.2f}")
        print(f"    Number of entries: {gl_entries.count()}")
        
        # Show sample entries
        for entry in gl_entries[:3]:
            print(f"      - {entry.description[:50]}: Debit GHS {entry.debit_amount:,.2f}, Balance GHS {entry.debit_amount:,.2f}")
    
    ap_total_from_gl += account_total

print(f"\n  TOTAL from General Ledger (all AP accounts): GHS {ap_total_from_gl:,.2f}")

# Compare
print("\n" + "=" * 80)
print("COMPARISON:")
print("=" * 80)
print(f"  AccountsPayable Model: GHS {ap_total_from_model:,.2f}")
print(f"  General Ledger: GHS {ap_total_from_gl:,.2f}")
print(f"  Expected (from image): GHS 600,834.40")

expected = Decimal('600834.40')

if abs(ap_total_from_model - expected) < 0.01:
    print(f"\n  [OK] AccountsPayable model matches expected value")
elif abs(ap_total_from_gl - expected) < 0.01:
    print(f"\n  [OK] General Ledger matches expected value")
    print(f"  [ACTION] Dashboard should use General Ledger, not AccountsPayable model")
else:
    print(f"\n  [WARN] Neither source matches expected value exactly")
    print(f"    Difference (Model): GHS {abs(ap_total_from_model - expected):,.2f}")
    print(f"    Difference (GL): GHS {abs(ap_total_from_gl - expected):,.2f}")

print("\n" + "=" * 80)
print("CHECK COMPLETE")
print("=" * 80)
