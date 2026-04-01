"""
Test and verify trial balance view doesn't show INVALID
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting import Account
from decimal import Decimal

# Try to import AdvancedGeneralLedger
try:
    from hospital.models_accounting_advanced import AdvancedGeneralLedger
    HAS_ADVANCED = True
except ImportError:
    HAS_ADVANCED = False

print("=" * 80)
print("TESTING TRIAL BALANCE DATA")
print("Checking for potential INVALID issues")
print("=" * 80)

# Test accounts 1200, 1201, 2000
test_accounts = ['1200', '1201', '2000']

for acc_code in test_accounts:
    print(f"\nTesting account {acc_code}...")
    print("-" * 80)
    
    account = Account.objects.filter(account_code=acc_code, is_deleted=False).first()
    if not account:
        print(f"  [ERROR] Account {acc_code} not found!")
        continue
    
    # Simulate what the view does
    if HAS_ADVANCED:
        adv_entries = AdvancedGeneralLedger.objects.filter(
            account=account,
            is_voided=False,
            is_deleted=False
        ).order_by('transaction_date', 'created')
        
        print(f"  Found {adv_entries.count()} AdvancedGeneralLedger entries")
        
        # Test accessing journal_entry for each entry
        errors = 0
        for entry in adv_entries[:5]:  # Test first 5
            try:
                if hasattr(entry, 'journal_entry') and entry.journal_entry:
                    journal_entry = entry.journal_entry
                    entry_number = getattr(journal_entry, 'entry_number', None)
                    ref_number = getattr(journal_entry, 'reference_number', None)
                    ref_type = getattr(journal_entry, 'entry_type', None)
                    
                    print(f"    Entry: {entry.description[:40]}")
                    print(f"      Entry Number: {entry_number}")
                    print(f"      Ref Number: {ref_number}")
                    print(f"      Ref Type: {ref_type}")
                else:
                    print(f"    Entry: {entry.description[:40]} - No journal_entry")
            except Exception as e:
                errors += 1
                print(f"    [ERROR] {entry.description[:40]}: {e}")
        
        if errors > 0:
            print(f"  [WARNING] Found {errors} errors accessing journal_entry")
        else:
            print(f"  [OK] No errors accessing journal_entry")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
