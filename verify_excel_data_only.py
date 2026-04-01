"""
Verify that only Excel-imported data remains
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
from decimal import Decimal

# Try to import AdvancedGeneralLedger
try:
    from hospital.models_accounting_advanced import AdvancedGeneralLedger
    HAS_ADVANCED = True
except ImportError:
    HAS_ADVANCED = False

print("=" * 80)
print("VERIFYING EXCEL DATA ONLY")
print("=" * 80)

# Check GeneralLedger
print("\n1. GeneralLedger entries:")
print("-" * 80)
gl_active = GeneralLedger.objects.filter(is_deleted=False)
print(f"  Active entries: {gl_active.count()}")

if gl_active.exists():
    for entry in gl_active[:10]:
        print(f"    - {entry.account.account_code}: DR {entry.debit_amount:,.2f} / CR {entry.credit_amount:,.2f} "
              f"(Ref: {entry.reference_number or 'N/A'})")

# Check AdvancedGeneralLedger
if HAS_ADVANCED:
    print("\n2. AdvancedGeneralLedger entries:")
    print("-" * 80)
    adv_active = AdvancedGeneralLedger.objects.filter(is_voided=False, is_deleted=False)
    print(f"  Active entries: {adv_active.count()}")
    
    if adv_active.exists():
        # Group by account
        accounts_with_entries = {}
        for entry in adv_active:
            acc_code = entry.account.account_code
            if acc_code not in accounts_with_entries:
                accounts_with_entries[acc_code] = []
            accounts_with_entries[acc_code].append(entry)
        
        for acc_code, entries in sorted(accounts_with_entries.items()):
            debits = sum(e.debit_amount for e in entries)
            credits = sum(e.credit_amount for e in entries)
            if entries[0].account.account_type in ['asset', 'expense']:
                balance = debits - credits
            else:
                balance = credits - debits
            
            print(f"\n  {acc_code} - {entries[0].account.account_name}")
            print(f"    Entries: {len(entries)}")
            print(f"    Debits: GHS {debits:,.2f}")
            print(f"    Credits: GHS {credits:,.2f}")
            print(f"    Balance: GHS {balance:,.2f}")

# Check revenue accounts
print("\n3. Revenue accounts status:")
print("-" * 80)
revenue_accounts = Account.objects.filter(account_type='revenue', is_deleted=False)
for account in revenue_accounts:
    gl_entries = GeneralLedger.objects.filter(account=account, is_deleted=False)
    if HAS_ADVANCED:
        adv_entries = AdvancedGeneralLedger.objects.filter(
            account=account, is_voided=False, is_deleted=False
        )
    else:
        adv_entries = []
    
    if gl_entries.exists() or (HAS_ADVANCED and adv_entries.exists()):
        print(f"  [WARNING] {account.account_code} - {account.account_name} still has entries!")
        print(f"    GL entries: {gl_entries.count()}")
        if HAS_ADVANCED:
            print(f"    Adv entries: {adv_entries.count()}")
    else:
        print(f"  [OK] {account.account_code} - {account.account_name}: No entries (cleared)")

print("\n" + "=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)
